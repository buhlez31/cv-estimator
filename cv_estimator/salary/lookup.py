"""CZ-ISCO + seniority score → SalaryEstimate from ISPV quantile table."""

from functools import lru_cache

import pandas as pd

from cv_estimator.config import DATA_DIR, SALARY_CEILING, SALARY_FLOOR
from cv_estimator.models import SalaryEstimate

ISPV_CSV = DATA_DIR / "ispv_2025.csv"
ISPV_PERIOD = "rok 2025"
ISPV_SPHERE = "MZDOVA"  # private-sector wages


@lru_cache(maxsize=1)
def _load_ispv() -> pd.DataFrame:
    if not ISPV_CSV.exists():
        raise FileNotFoundError(
            f"ISPV CSV missing at {ISPV_CSV}. "
            "Run scripts/prepare_ispv_data.py or commit data/ispv_2025.csv."
        )
    df = pd.read_csv(ISPV_CSV, dtype={"cz_isco_code": str})
    df = df.set_index("cz_isco_code")
    return df


def _lookup_row(cz_isco: str) -> pd.Series:
    """Find the row for a CZ-ISCO 4-digit code, falling back to the prefix."""
    df = _load_ispv()
    if cz_isco in df.index:
        return df.loc[cz_isco]
    # Fallback: try 3-digit prefix matches, pick the first
    prefix = cz_isco[:3]
    candidates = [c for c in df.index if c.startswith(prefix)]
    if candidates:
        return df.loc[candidates[0]]
    # Final fallback: 2519 (generic SW dev)
    return df.loc["2519"]


def estimate_salary(cz_isco: str, seniority_score: int) -> SalaryEstimate:
    """Map (cz_isco, seniority_score 0-100) → SalaryEstimate range."""
    row = _lookup_row(cz_isco)
    p25, p50, p75, p90 = int(row["p25"]), int(row["p50"]), int(row["p75"]), int(row["p90"])
    median, percentile = _interpolate(seniority_score, p25, p50, p75, p90)

    # Range = ±15% around the interpolated median, clamped to (p25, p90)
    low = max(p25, int(median * 0.85))
    high = min(p90, int(median * 1.15))

    # Sanity clamp
    low = max(SALARY_FLOOR, low)
    high = min(SALARY_CEILING, high)
    median = max(low, min(high, median))

    return SalaryEstimate(
        low=low,
        median=median,
        high=high,
        currency="CZK",
        percentile_position=percentile,
    )


def _interpolate(score: int, p25: int, p50: int, p75: int, p90: int) -> tuple[int, int]:
    """Linear-interpolate seniority_score (0-100) onto the ISPV quantile curve.

    Returns (estimated_median_CZK, percentile_position 25-90).
    Anchors: score 25→P25, 50→P50, 75→P75, 90→P90. Linear in between.
    """
    score = max(0, min(100, score))
    anchors = [
        (0, p25, 25),
        (25, p25, 25),
        (50, p50, 50),
        (75, p75, 75),
        (90, p90, 90),
        (100, p90, 90),
    ]
    for i in range(len(anchors) - 1):
        s_low, v_low, perc_low = anchors[i]
        s_high, v_high, perc_high = anchors[i + 1]
        if s_low <= score <= s_high:
            if s_high == s_low:
                return int(v_low), perc_low
            frac = (score - s_low) / (s_high - s_low)
            value = int(v_low + frac * (v_high - v_low))
            percentile = int(perc_low + frac * (perc_high - perc_low))
            return value, percentile
    return int(p50), 50
