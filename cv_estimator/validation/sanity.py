"""Output sanity checks — last line of defense before returning CVAnalysis."""

from cv_estimator.config import SALARY_CEILING, SALARY_FLOOR
from cv_estimator.models import CVAnalysis, TrackResult


class SanityError(ValueError):
    """Raised when a pipeline output violates an obvious invariant."""


def validate(result: CVAnalysis) -> None:
    """Cheap output range checks. Raises SanityError on hard violations."""
    _check_track(result.track_explicit, label="track_explicit")
    _check_track(result.track_with_inferred, label="track_with_inferred")

    # Hidden-assets track should not score below the skeptical baseline —
    # inferred bonus is additive, never subtractive.
    if result.track_with_inferred.seniority_score < result.track_explicit.seniority_score:
        raise SanityError(
            "track_with_inferred.seniority_score < track_explicit.seniority_score — "
            "inferred bonus should be non-negative."
        )

    if len(result.recommendations) != 3:
        raise SanityError(f"Expected exactly 3 recommendations, got {len(result.recommendations)}")
    if not (3 <= len(result.strengths) <= 5):
        raise SanityError(f"strengths must be 3-5 items, got {len(result.strengths)}")
    if not (3 <= len(result.gaps) <= 5):
        raise SanityError(f"gaps must be 3-5 items, got {len(result.gaps)}")


def _check_track(track: TrackResult, *, label: str) -> None:
    _check_score(track.seniority_score, f"{label}.seniority_score")
    _check_score(int(track.breakdown.years_experience), f"{label}.breakdown.years_experience")
    _check_score(int(track.breakdown.skills_depth), f"{label}.breakdown.skills_depth")
    _check_score(int(track.breakdown.role_progression), f"{label}.breakdown.role_progression")
    _check_score(int(track.breakdown.education), f"{label}.breakdown.education")

    s = track.salary_estimate
    if not (SALARY_FLOOR <= s.low <= s.median <= s.high <= SALARY_CEILING):
        raise SanityError(
            f"{label}.salary_estimate out of bounds: low={s.low} median={s.median} "
            f"high={s.high} (floor={SALARY_FLOOR}, ceiling={SALARY_CEILING})"
        )
    if not (s.market_p25 <= s.market_p50 <= s.market_p75 <= s.market_p90):
        raise SanityError(
            f"{label}.salary_estimate market band out of order: "
            f"p25={s.market_p25} p50={s.market_p50} p75={s.market_p75} p90={s.market_p90}"
        )


def _check_score(value: int, name: str) -> None:
    if not 0 <= value <= 100:
        raise SanityError(f"{name} out of range [0, 100]: {value}")
