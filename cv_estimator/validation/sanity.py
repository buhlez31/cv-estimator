"""Output sanity checks — last line of defense before returning CVAnalysis."""

from cv_estimator.config import SALARY_CEILING, SALARY_FLOOR
from cv_estimator.models import CVAnalysis


class SanityError(ValueError):
    """Raised when a pipeline output violates an obvious invariant."""


def validate(result: CVAnalysis) -> None:
    """Cheap output range checks. Raises SanityError on hard violations."""
    _check_score(result.seniority_score, "seniority_score")
    _check_score(int(result.breakdown.years_experience), "breakdown.years_experience")
    _check_score(int(result.breakdown.skills_depth), "breakdown.skills_depth")
    _check_score(int(result.breakdown.role_progression), "breakdown.role_progression")
    _check_score(int(result.breakdown.education), "breakdown.education")

    s = result.salary_estimate
    if not (SALARY_FLOOR <= s.low <= s.median <= s.high <= SALARY_CEILING):
        raise SanityError(
            f"Salary range out of bounds: low={s.low} median={s.median} high={s.high} "
            f"(floor={SALARY_FLOOR}, ceiling={SALARY_CEILING})"
        )

    if len(result.recommendations) != 3:
        raise SanityError(f"Expected exactly 3 recommendations, got {len(result.recommendations)}")

    if not (3 <= len(result.strengths) <= 5):
        raise SanityError(f"strengths must be 3-5 items, got {len(result.strengths)}")
    if not (3 <= len(result.gaps) <= 5):
        raise SanityError(f"gaps must be 3-5 items, got {len(result.gaps)}")


def _check_score(value: int, name: str) -> None:
    if not 0 <= value <= 100:
        raise SanityError(f"{name} out of range [0, 100]: {value}")
