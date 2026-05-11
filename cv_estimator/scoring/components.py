"""Compute the 4 ScoreBreakdown components from extractor outputs.

Two entry points produce two ScoreBreakdowns:

- `compute_explicit_only` — buzzword baseline using only literal CV content.
  Objective view — no skepticism applied here, just degree of skill listing.
- `compute_with_inferred` — adds a confidence-weighted bonus from the
  hidden-assets pass. The inferred extraction itself is the only part of
  the pipeline that applies skepticism.

The weighted aggregate is in `seniority.py`.
"""

from cv_estimator.config import (
    EDUCATION_BASE_MAP,
    EDUCATION_EMPTY_FIELD_MULTIPLIER,
    EDUCATION_FIELD_MATCH_BONUS,
    EDUCATION_FIELD_MISMATCH_PENALTY,
    EDUCATION_PRESTIGE_BONUS,
    EXPLICIT_ONLY_SKILLS_CAP,
    FIELD_FAMILY_KEYWORDS,
    INFERRED_BONUS_CAP,
    INFERRED_BONUS_PER_CAPABILITY,
    JUNIOR_TITLE_KEYWORDS,
    PRESTIGE_INSTITUTION_KEYWORDS,
    ROLE_FAMILY_KEYWORDS,
    ROLE_FIELD_ADJACENT_PAIRS,
    SENIOR_TITLE_KEYWORDS,
    SKILL_TIERS_HIGH,
    SKILL_TIERS_LOW,
    SKILL_TIERS_MID,
    YEARS_CAP,
)
from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown


def compute_explicit_only(explicit: ExplicitData, analysis_role: str) -> ScoreBreakdown:
    """Buzzword baseline — uses only what is literally in the CV.

    Skills capped at EXPLICIT_ONLY_SKILLS_CAP (75) to encode the rule
    that a bare skill list, without project-narrative evidence, is
    inherently incomplete signal. The remaining 25 points of headroom
    are only reachable on the with-inferred track when hidden assets
    surface genuine project depth.

    `analysis_role` drives the education field-relevance modifier.
    """
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience),
        skills_depth=_explicit_skills_score(explicit.explicit_skills, cap=EXPLICIT_ONLY_SKILLS_CAP),
        role_progression=_role_progression_score(
            explicit.role, explicit.role_seniority_signal, explicit.years_experience
        ),
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
    """Optimistic ceiling — explicit skills (cap 100) plus confidence-weighted
    inferred bonus on top, also capped so a single noisy LLM pass cannot
    inflate skills_depth past saturation."""
    explicit_skills = _explicit_skills_score(explicit.explicit_skills, cap=100.0)
    bonus = _inferred_bonus(inferred)
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience),
        skills_depth=min(100.0, explicit_skills + bonus),
        role_progression=_role_progression_score(
            explicit.role, explicit.role_seniority_signal, explicit.years_experience
        ),
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


def _years_score(years: int) -> float:
    """Continuous, capped at YEARS_CAP (15)."""
    return float(min(years, YEARS_CAP) / YEARS_CAP * 100)


def _explicit_skills_score(skills: list[str], *, cap: float) -> float:
    """Tier-weighted score for skills that literally appear in the CV,
    clamped to the caller-supplied cap. The explicit-only track passes
    EXPLICIT_ONLY_SKILLS_CAP (75); the with-inferred track passes 100."""
    base = 0.0
    seen: set[str] = set()
    for raw in skills:
        s = raw.strip().lower()
        if s in seen:
            continue
        seen.add(s)
        if s in SKILL_TIERS_HIGH:
            base += 25
        elif s in SKILL_TIERS_MID:
            base += 15
        elif s in SKILL_TIERS_LOW:
            base += 5
        else:
            base += 8  # unknown skill — partial credit, don't ignore
    return float(min(cap, base))


def _inferred_bonus(inferred: InferredData) -> float:
    """Confidence-weighted bonus from inferred capabilities, capped at
    INFERRED_BONUS_CAP.

    must_have capabilities contribute the full multiplier; nice_to_have
    capabilities contribute half, so role-critical signal dominates
    soft / adjacent signal in the score.
    """
    raw = 0.0
    for cap in inferred.inferred_capabilities:
        weight = INFERRED_BONUS_PER_CAPABILITY * cap.confidence
        if cap.relevance == "nice_to_have":
            weight *= 0.5
        raw += weight
    return min(INFERRED_BONUS_CAP, raw)


def _role_progression_score(role: str, signal: str, years: int) -> float:
    """Junior→Mid→Senior signal, anchored on title keywords + years."""
    low = role.lower()
    if signal == "principal":
        return 95.0
    if signal == "senior" or any(kw in low for kw in SENIOR_TITLE_KEYWORDS):
        return 80.0 + (5.0 if years >= 10 else 0.0)
    if signal == "junior" or any(kw in low for kw in JUNIOR_TITLE_KEYWORDS):
        return 25.0
    if signal == "mid":
        return 55.0
    # unknown — infer from years alone
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
