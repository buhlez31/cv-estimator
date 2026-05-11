"""Compute the 4 ScoreBreakdown components from extractor outputs.

Each component is normalized to 0-100. The weighted aggregate happens in
`seniority.py` using the fixed weights from `config.py`.
"""

from cv_estimator.config import (
    HIGHER_ED_KEYWORDS,
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


def compute(explicit: ExplicitData, inferred: InferredData) -> ScoreBreakdown:
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience),
        skills_depth=_skills_score(explicit.explicit_skills, inferred),
        role_progression=_role_progression_score(
            explicit.role, explicit.role_seniority_signal, explicit.years_experience
        ),
        education=_education_score(explicit.highest_education, explicit.institution),
    )


def _years_score(years: int) -> float:
    """Continuous, capped at YEARS_CAP (15)."""
    return float(min(years, YEARS_CAP) / YEARS_CAP * 100)


def _skills_score(skills: list[str], inferred: InferredData) -> float:
    """Tier-weighted explicit skills + bonus for high-confidence inferred capabilities."""
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
            base += 8  # unknown skill — give partial credit, don't ignore
    # Inferred bonus: up to +15 pts for hidden assets with confidence ≥ 0.6
    bonus = sum(5 for c in inferred.inferred_capabilities if c.confidence >= 0.6)
    return float(min(100, base + min(15, bonus)))


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
    # Sanity guard: institution-only signal (no degree label) for users who write only "MIT, 2018"
    if highest == "none" and any(kw in inst_low for kw in HIGHER_ED_KEYWORDS):
        base = max(base, 60.0)
    return base
