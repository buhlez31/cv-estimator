"""Weighted aggregate of the 4 ScoreBreakdown components → seniority score (0-100)."""

from cv_estimator.config import (
    WEIGHT_EDUCATION,
    WEIGHT_ROLE,
    WEIGHT_SKILLS,
    WEIGHT_YEARS,
)
from cv_estimator.models import ScoreBreakdown


def compute(breakdown: ScoreBreakdown) -> int:
    score = (
        breakdown.years_experience * WEIGHT_YEARS
        + breakdown.skills_depth * WEIGHT_SKILLS
        + breakdown.role_progression * WEIGHT_ROLE
        + breakdown.education * WEIGHT_EDUCATION
    )
    return int(round(max(0.0, min(100.0, score))))
