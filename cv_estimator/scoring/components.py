"""Compute the 4 ScoreBreakdown components from extractor outputs.

Two entry points produce two ScoreBreakdowns:

- `compute_explicit_only` — skeptical baseline using only literal CV content
- `compute_with_inferred` — adds a confidence-weighted bonus from the
  hidden-assets pass

The weighted aggregate is in `seniority.py`.
"""

from cv_estimator.config import (
    EXPLICIT_ONLY_SKILLS_CAP,
    HIGHER_ED_KEYWORDS,
    INFERRED_BONUS_CAP,
    INFERRED_BONUS_PER_CAPABILITY,
    JUNIOR_TITLE_KEYWORDS,
    PRESTIGE_INSTITUTION_KEYWORDS,
    SENIOR_TITLE_KEYWORDS,
    SKILL_TIERS_HIGH,
    SKILL_TIERS_LOW,
    SKILL_TIERS_MID,
    YEARS_CAP,
)
from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown


def compute_explicit_only(explicit: ExplicitData) -> ScoreBreakdown:
    """Skeptical baseline — uses only what is literally in the CV.

    Skills capped at EXPLICIT_ONLY_SKILLS_CAP (75) to encode the rule
    that a bare skill list, without project-narrative evidence, is
    inherently incomplete signal. The remaining 25 points of headroom
    are only reachable on the with-inferred track when hidden assets
    surface genuine project depth.
    """
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience),
        skills_depth=_explicit_skills_score(explicit.explicit_skills, cap=EXPLICIT_ONLY_SKILLS_CAP),
        role_progression=_role_progression_score(
            explicit.role, explicit.role_seniority_signal, explicit.years_experience
        ),
        education=_education_score(explicit.highest_education, explicit.institution),
    )


def compute_with_inferred(explicit: ExplicitData, inferred: InferredData) -> ScoreBreakdown:
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
        education=_education_score(explicit.highest_education, explicit.institution),
    )


# Backwards-compatible alias for any external caller — internal pipeline
# uses the two explicit entry points above.
def compute(explicit: ExplicitData, inferred: InferredData) -> ScoreBreakdown:
    return compute_with_inferred(explicit, inferred)


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


def _education_score(highest: str, institution: str) -> float:
    base_map = {"none": 0.0, "high_school": 15.0, "bachelor": 60.0, "master": 85.0, "phd": 95.0}
    base = base_map.get(highest, 30.0)
    inst_low = (institution or "").lower()
    if any(kw in inst_low for kw in PRESTIGE_INSTITUTION_KEYWORDS):
        base = min(100.0, base + 5.0)
    if highest == "none" and any(kw in inst_low for kw in HIGHER_ED_KEYWORDS):
        base = max(base, 60.0)
    return base
