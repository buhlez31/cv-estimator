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
        market_p25=p25,
        market_p50=p50,
        market_p75=p75,
        market_p90=p90,
    )


def _interpolate(score: int, p25: int, p50: int, p75: int, p90: int) -> tuple[int, int]:
    """Map seniority_score (0-100) to a market salary point.

    Uses **seniority-bucket anchors**, not a continuous linear curve, so a
    mid-tier engineer doesn't land at P75 just because the score happens to
    sit at 75:

    - Junior (0-40)     → P25 (entry-level wage band)
    - Mid (40-70)       → P25 → P50 (interpolated)
    - Senior (70-90)    → P50 → P75 (interpolated)
    - Principal (90-100)→ P75 → P90 (interpolated)

    Trade-off: fewer candidates earn a P75+ estimate, which matches the
    real market shape (most senior ICs sit between P50 and P75, P90 is
    reserved for principal / staff-level outliers). Calibrated against
    public Czech IT salary surveys.
    """
    score = max(0, min(100, score))
    anchors = [
        (0, p25, 25),
        (40, p25, 25),
        (70, p50, 50),
        (90, p75, 75),
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
