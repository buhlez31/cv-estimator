"""Compute the 4 ScoreBreakdown components from extractor outputs.

Two entry points produce two ScoreBreakdowns:

- `compute_explicit_only` — buzzword baseline using only literal CV content.
  Objective view — no skepticism applied here, just degree of skill listing.
- `compute_with_inferred` — adds a confidence-weighted bonus from the
  hidden-assets pass. The inferred extraction itself is the only part of
  the pipeline that applies skepticism.

The weighted aggregate is in `seniority.py`.
"""

from functools import lru_cache

from cv_estimator.config import (
    EDUCATION_BASE_MAP,
    EDUCATION_EMPTY_FIELD_MULTIPLIER,
    EDUCATION_FIELD_MATCH_BONUS,
    EDUCATION_FIELD_MISMATCH_PENALTY,
    EDUCATION_PRESTIGE_BONUS,
    FIELD_FAMILY_KEYWORDS,
    INFERRED_COVERAGE_CONFIDENCE_THRESHOLD,
    JUNIOR_TITLE_KEYWORDS,
    PRESTIGE_INSTITUTION_KEYWORDS,
    ROLE_FAMILY_KEYWORDS,
    ROLE_FIELD_ADJACENT_PAIRS,
    SENIOR_TITLE_KEYWORDS,
    YEARS_CAP_BY_LEVEL,
)
from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown

# Title keywords used by `_role_progression_score` and `_expected_years_cap`
# to bucket the analyzed role. `SENIOR_TITLE_KEYWORDS` lives in config.py;
# this set covers the principal / staff / VP tier above it.
_PRINCIPAL_TITLE_KEYWORDS = {"principal", "staff", "chief", "vp", "head of"}


def compute_explicit_only(explicit: ExplicitData, analysis_role: str) -> ScoreBreakdown:
    """Buzzword baseline — uses only what is literally in the CV.

    skills_depth is an LLM-driven coverage percent (single mechanism for
    all role families). `analysis_role` drives the LLM coverage prompt
    plus the education field-relevance modifier.
    """
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience, analysis_role),
        skills_depth=_skills_coverage_score(
            explicit.explicit_skills, [], analysis_role, include_inferred=False
        ),
        role_progression=_role_progression_score(analysis_role, explicit.years_experience),
        education=_education_score(
            explicit.highest_education,
            explicit.institution,
            explicit.field_of_study,
            analysis_role,
        ),
    )


def compute_with_inferred(
    explicit: ExplicitData,
    inferred: InferredData,
    analysis_role: str,
) -> ScoreBreakdown:
    """Hidden-assets-included view — confident inferred capabilities
    (≥ INFERRED_COVERAGE_CONFIDENCE_THRESHOLD) feed into the LLM coverage
    prompt as supporting evidence, and the model decides how much they
    lift the score."""
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience, analysis_role),
        skills_depth=_skills_coverage_score(
            explicit.explicit_skills,
            inferred.inferred_capabilities,
            analysis_role,
            include_inferred=True,
        ),
        role_progression=_role_progression_score(analysis_role, explicit.years_experience),
        education=_education_score(
            explicit.highest_education,
            explicit.institution,
            explicit.field_of_study,
            analysis_role,
        ),
    )


# Backwards-compatible alias for any external caller — internal pipeline
# uses the two explicit entry points above.
def compute(
    explicit: ExplicitData,
    inferred: InferredData,
    analysis_role: str | None = None,
) -> ScoreBreakdown:
    return compute_with_inferred(explicit, inferred, analysis_role or explicit.role)


# ----- Internals ---------------------------------------------------------


def _years_score(years: int, analysis_role: str) -> float:
    """Continuous, capped by what the analyzed role expects.

    Junior roles saturate at 3 yrs, senior at 15, principal at 20.
    Same CV → different score for the same candidate depending on the
    target / detected role.
    """
    cap = _expected_years_cap(analysis_role)
    return float(min(years, cap) / cap * 100)


def _expected_years_cap(analysis_role: str) -> int:
    low = (analysis_role or "").lower()
    if any(kw in low for kw in _PRINCIPAL_TITLE_KEYWORDS):
        return YEARS_CAP_BY_LEVEL["principal"]
    if any(kw in low for kw in SENIOR_TITLE_KEYWORDS):
        return YEARS_CAP_BY_LEVEL["senior"]
    if any(kw in low for kw in JUNIOR_TITLE_KEYWORDS):
        return YEARS_CAP_BY_LEVEL["junior"]
    return YEARS_CAP_BY_LEVEL["mid"]


def _skills_coverage_score(
    explicit_skills: list[str],
    inferred_capabilities: list,
    analysis_role: str,
    *,
    include_inferred: bool,
) -> float:
    """LLM-driven skills coverage scoring (single mechanism, all role families).

    Every role routes through `_llm_coverage_raw`, which queries the model
    with the role + signals and returns the coverage percent plus
    attribution (value-adding capabilities + concerns). Overclaim
    skepticism lives in the prompt, not in Python.
    """
    score, _, _ = _llm_coverage_raw(
        analysis_role,
        tuple(s.strip().lower() for s in explicit_skills if s.strip()),
        (
            tuple(
                (c.skill.strip().lower(), round(c.confidence, 2))
                for c in inferred_capabilities
                if c.confidence >= INFERRED_COVERAGE_CONFIDENCE_THRESHOLD
            )
            if include_inferred
            else ()
        ),
        include_inferred=include_inferred,
    )
    return score


@lru_cache(maxsize=128)
def _llm_coverage_raw(
    role: str,
    explicit_skills_tuple: tuple[str, ...],
    inferred_caps_tuple: tuple[tuple[str, float], ...],
    *,
    include_inferred: bool,
) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    """LLM-based skills coverage scoring — single mechanism for all roles.

    Returns (coverage_percent, value_adding tuple, concerns tuple). The
    LLM call is made ONCE per (role, skills, inferred, include_inferred)
    via lru_cache; subsequent calls (e.g. for attribution) reuse the
    cached response — no double-billing.

    Lazy import of `llm` so test fixtures that mock the prompt don't
    need an Anthropic client at import time.
    """
    import json as _json

    from cv_estimator import llm

    inferred_payload = [{"skill": s, "confidence": c} for s, c in inferred_caps_tuple]
    prompt = llm.render_prompt(
        "skills_coverage",
        role=role,
        explicit_skills=_json.dumps(list(explicit_skills_tuple), ensure_ascii=False),
        inferred_capabilities=_json.dumps(inferred_payload, ensure_ascii=False),
    )
    payload = llm.call_json(prompt)
    score = max(0.0, min(100.0, float(payload.get("coverage_percent", 0) or 0)))
    value_adding = tuple(str(x) for x in (payload.get("value_adding_capabilities") or []))
    concerns = tuple(str(x) for x in (payload.get("concerns") or []))
    return score, value_adding, concerns


def coverage_attribution_for(
    role: str,
    explicit_skills: list[str],
    inferred_capabilities: list,
    *,
    include_inferred: bool,
):
    """Return a `CoverageAttribution` for any role.

    Pipeline calls this after compute_*; the underlying LLM response is
    already cached from the skills-coverage scoring call, so this is
    free.
    """
    from cv_estimator.models import CoverageAttribution

    skills_tuple = tuple(s.strip().lower() for s in explicit_skills if s.strip())
    inferred_tuple = (
        tuple(
            (c.skill.strip().lower(), round(c.confidence, 2))
            for c in inferred_capabilities
            if c.confidence >= INFERRED_COVERAGE_CONFIDENCE_THRESHOLD
        )
        if include_inferred
        else ()
    )
    _, value_adding, concerns = _llm_coverage_raw(
        role,
        skills_tuple,
        inferred_tuple,
        include_inferred=include_inferred,
    )
    return CoverageAttribution(
        value_adding=list(value_adding),
        concerns=list(concerns),
    )


def _role_progression_score(analysis_role: str, years: int) -> float:
    """Junior→Mid→Senior signal driven by the analyzed role's level + years.

    The metric reflects the seniority of the role being analyzed (target
    when supplied, otherwise the auto-detected one). A candidate's CV
    seniority signal does NOT short-circuit this — the answer to "what
    level does this analysis target?" comes from the analysis role
    itself.
    """
    low = (analysis_role or "").lower()
    if any(kw in low for kw in _PRINCIPAL_TITLE_KEYWORDS):
        return 95.0
    if any(kw in low for kw in SENIOR_TITLE_KEYWORDS):
        return 80.0 + (5.0 if years >= 10 else 0.0)
    if any(kw in low for kw in JUNIOR_TITLE_KEYWORDS):
        return 25.0
    # No explicit level keyword in the role → fall back to years.
    if years >= 10:
        return 75.0
    if years >= 5:
        return 55.0
    if years >= 2:
        return 35.0
    return 20.0


def _education_score(
    highest: str,
    institution: str,
    field_of_study: str,
    analysis_role: str,
) -> float:
    """Education score = base degree value + prestige + field-relevance modifier.

    - Lowered base map (master = 50, not 85) so prestige + field bonus
      lands the typical case around 55-65, not 90.
    - Empty field_of_study → half credit (we know the degree level but
      can't judge relevance for the role).
    - Match (same family or role-family unknown / field-family unknown)
      → +5 only for direct match.
    - Adjacent (e.g. tech_adjacent + tech) → 0 modifier.
    - Mismatch (clearly wrong field for role) → -25 hard penalty,
      "irrelevant education shouldn't carry weight".
    - "none" → 0, never lifted by prestige / field bonus (safety floor
      stays at 60 only when institution looks academic but degree label
      missing — narrow safety net for sparse CVs).
    """
    if highest == "none":
        # No degree → 0. Per user direction: "kdo nema education uvedeny
        # tak 0 za education navic". No institution-only safety net.
        return 0.0

    base = EDUCATION_BASE_MAP.get(highest, 0.0)
    inst_low = (institution or "").lower()
    if any(kw in inst_low for kw in PRESTIGE_INSTITUTION_KEYWORDS):
        base += EDUCATION_PRESTIGE_BONUS

    if not (field_of_study or "").strip():
        # No field info — half credit. Known degree level alone is half signal.
        return max(0.0, min(100.0, base * EDUCATION_EMPTY_FIELD_MULTIPLIER))

    role_family = _classify_role_family(analysis_role)
    field_family = _classify_field_family(field_of_study)

    if role_family == "unknown" or field_family == "unknown":
        modifier = 0.0
    elif role_family == field_family:
        modifier = EDUCATION_FIELD_MATCH_BONUS
    elif (role_family, field_family) in ROLE_FIELD_ADJACENT_PAIRS:
        modifier = 0.0
    else:
        modifier = -EDUCATION_FIELD_MISMATCH_PENALTY

    return max(0.0, min(100.0, base + modifier))


def _classify_role_family(role: str) -> str:
    """Return the family bucket for a role title via substring keyword match."""
    low = (role or "").lower()
    for family, keywords in ROLE_FAMILY_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return family
    return "unknown"


def _classify_field_family(field: str) -> str:
    """Return the family bucket for a field-of-study via substring match."""
    low = (field or "").lower()
    if not low.strip():
        return "unknown"
    for family, keywords in FIELD_FAMILY_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return family
    return "unknown"
