"""Thin orchestrator — sequences the 4 (or 5) LLM passes + scoring + salary
lookup.

Per the design doc: this file is a table of contents, NOT a place for logic.
Each step is a single call into a domain module.

A single `analysis_role` drives the entire pipeline downstream of extraction:
- when the user supplies `target_role`, that string is the analysis role and
  LLM #5 (match assessment) runs;
- otherwise, the auto-detected role from LLM #1 is the analysis role and
  LLM #5 is skipped.

Both scoring tracks (explicit baseline + with-inferred ceiling) operate
against the same analysis role so the salary anchors on a single CZ-ISCO.
"""

import time

from cv_estimator.explanation import match_assess, narrative, roadmap
from cv_estimator.extractors import document, explicit, inferred
from cv_estimator.models import CVAnalysis, TargetRoleMatch, TrackResult
from cv_estimator.salary import lookup, market_postings, role_mapping
from cv_estimator.scoring import components, seniority
from cv_estimator.validation import sanity


def analyze_cv(
    file_bytes: bytes,
    filename: str,
    *,
    target_role: str | None = None,
    region: str | None = None,
) -> CVAnalysis:
    """Run the full pipeline. Returns a validated CVAnalysis.

    When `target_role` is provided, the entire analysis is anchored on that
    role (CZ-ISCO lookup, salary band, hidden-assets scoping) and LLM #5
    emits a match assessment. When omitted, the auto-detected best-fit role
    drives everything.
    """
    started = time.time()

    raw_text = document.extract_text(file_bytes, filename)
    language = document.detect_language(raw_text)

    explicit_data = explicit.extract(raw_text, language)

    # Resolve the single role driving the rest of the pipeline.
    if target_role:
        analysis_role = target_role
        role_source = "target"
    else:
        analysis_role = explicit_data.role
        role_source = "detected"

    # Hidden-assets pass is scoped to analysis_role — capabilities outside
    # this role's domain are dropped per the extract_inferred prompt.
    inferred_data = inferred.extract(raw_text, analysis_role, language)

    cz_isco = role_mapping.map_to_cz_isco(analysis_role)

    # Track A: buzzword baseline — objective view from literal CV content.
    breakdown_explicit = components.compute_explicit_only(explicit_data, analysis_role)
    score_explicit = seniority.compute(breakdown_explicit)
    salary_explicit = lookup.estimate_salary(
        cz_isco, score_explicit, role=analysis_role, region=region
    )
    attr_explicit = components.coverage_attribution_for(
        analysis_role, explicit_data.explicit_skills, [], include_inferred=False
    )

    # Track B: optimistic ceiling (adds confidence-weighted inferred bonus).
    breakdown_full = components.compute_with_inferred(explicit_data, inferred_data, analysis_role)
    score_full = seniority.compute(breakdown_full)
    salary_full = lookup.estimate_salary(cz_isco, score_full, role=analysis_role, region=region)
    attr_full = components.coverage_attribution_for(
        analysis_role,
        explicit_data.explicit_skills,
        inferred_data.inferred_capabilities,
        include_inferred=True,
    )

    # Narrative + recommendations consume the fuller picture so roadmap advice
    # covers the hidden-asset trajectory, not just the conservative baseline.
    # Both use `analysis_role` (target if supplied, else detected) so strengths,
    # gaps and recommendations align with the role driving the rest of the
    # pipeline — not the auto-detected role from the CV.
    sg = narrative.analyze(explicit_data, inferred_data, breakdown_full, score_full, analysis_role)
    recs = roadmap.generate(explicit_data, sg.gaps, score_full, cz_isco, analysis_role)

    # LLM #5: only when the user supplied a target role.
    target: TargetRoleMatch | None = None
    if target_role:
        match = match_assess.evaluate(target_role, explicit_data, inferred_data)
        target = TargetRoleMatch(
            target_role=target_role,
            target_cz_isco=cz_isco,
            match_score=match.match_score,
            rationale=match.rationale,
        )

    # Layer C — optional live posting cross-check. Skips silently when
    # APIFY_TOKEN is unset; failure here never breaks the pipeline. When
    # data is available we nudge both track medians toward the live signal
    # (30 % weight) so the displayed salary reflects present-day jobs.cz
    # without bloating the UI with an extra panel.
    postings = market_postings.fetch_market_postings(analysis_role, region)
    salary_explicit = lookup.blend_with_postings(salary_explicit, postings)
    salary_full = lookup.blend_with_postings(salary_full, postings)

    result = CVAnalysis(
        analysis_role=analysis_role,
        cz_isco_code=cz_isco,
        role_source=role_source,
        detected_role=explicit_data.role,
        role_confidence=1.0 if cz_isco != "2519" else 0.6,
        language=explicit_data.language,
        explicit_skills=explicit_data.explicit_skills,
        inferred_capabilities=inferred_data.inferred_capabilities,
        track_explicit=TrackResult(
            seniority_score=score_explicit,
            breakdown=breakdown_explicit,
            salary_estimate=salary_explicit,
            coverage_attribution=attr_explicit,
        ),
        track_with_inferred=TrackResult(
            seniority_score=score_full,
            breakdown=breakdown_full,
            salary_estimate=salary_full,
            coverage_attribution=attr_full,
        ),
        target=target,
        strengths=sg.strengths,
        gaps=sg.gaps,
        recommendations=recs,
        market_postings=postings,
        processing_metadata={
            "filename": filename,
            "elapsed_seconds": round(time.time() - started, 2),
            "raw_text_chars": len(raw_text),
            "ispv_period": lookup.ISPV_PERIOD,
            "ispv_sphere": lookup.ISPV_SPHERE,
            "target_role_provided": target_role is not None,
            "region": region,
            "live_postings_available": postings is not None,
        },
    )
    sanity.validate(result)
    return result
