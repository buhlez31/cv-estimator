"""Thin orchestrator — sequences the 4 LLM passes + scoring + salary lookup.

Per the design doc: this file is a table of contents, NOT a place for logic.
Each step is a single call into a domain module.

After Branch A: two parallel scoring/salary tracks are emitted so the reader
can compare the skeptical buzzword baseline against the hidden-assets
ceiling. Narrative + recommendations still consume the fuller picture so
roadmap advice covers both axes.
"""

import time

from cv_estimator.explanation import narrative, roadmap
from cv_estimator.extractors import document, explicit, inferred
from cv_estimator.models import CVAnalysis, TrackResult
from cv_estimator.salary import lookup, role_mapping
from cv_estimator.scoring import components, seniority
from cv_estimator.validation import sanity


def analyze_cv(file_bytes: bytes, filename: str) -> CVAnalysis:
    """Run the full pipeline. Returns a validated CVAnalysis."""
    started = time.time()

    raw_text = document.extract_text(file_bytes, filename)
    language = document.detect_language(raw_text)

    explicit_data = explicit.extract(raw_text, language)
    # Pass detected role to the inferred-capabilities pass so hidden assets
    # are scoped to the role the candidate is best-fit for, not generic.
    inferred_data = inferred.extract(raw_text, explicit_data.role, language)
    cz_isco = role_mapping.map_to_cz_isco(explicit_data.role)

    # Track A: skeptical baseline (only literal CV content).
    breakdown_explicit = components.compute_explicit_only(explicit_data)
    score_explicit = seniority.compute(breakdown_explicit)
    salary_explicit = lookup.estimate_salary(cz_isco, score_explicit)

    # Track B: optimistic ceiling (adds confidence-weighted inferred bonus).
    breakdown_full = components.compute_with_inferred(explicit_data, inferred_data)
    score_full = seniority.compute(breakdown_full)
    salary_full = lookup.estimate_salary(cz_isco, score_full)

    # Narrative + recommendations consume the fuller picture so roadmap advice
    # covers the hidden-asset trajectory, not just the conservative baseline.
    sg = narrative.analyze(explicit_data, inferred_data, breakdown_full, score_full)
    recs = roadmap.generate(explicit_data, sg.gaps, score_full, cz_isco)

    result = CVAnalysis(
        detected_role=explicit_data.role,
        cz_isco_code=cz_isco,
        role_confidence=1.0 if cz_isco != "2519" else 0.6,
        language=explicit_data.language,
        explicit_skills=explicit_data.explicit_skills,
        inferred_capabilities=inferred_data.inferred_capabilities,
        track_explicit=TrackResult(
            seniority_score=score_explicit,
            breakdown=breakdown_explicit,
            salary_estimate=salary_explicit,
        ),
        track_with_inferred=TrackResult(
            seniority_score=score_full,
            breakdown=breakdown_full,
            salary_estimate=salary_full,
        ),
        strengths=sg.strengths,
        gaps=sg.gaps,
        recommendations=recs,
        processing_metadata={
            "filename": filename,
            "elapsed_seconds": round(time.time() - started, 2),
            "raw_text_chars": len(raw_text),
            "ispv_period": lookup.ISPV_PERIOD,
            "ispv_sphere": lookup.ISPV_SPHERE,
        },
    )
    sanity.validate(result)
    return result
