"""CZ-ISCO + seniority score → SalaryEstimate from ISPV quantile table.

Three layers feed the final number:
  1. ISPV base distribution per CZ-ISCO (P10/P25/P50/P75/P90/mean + sample_n)
  2. Bonus + supplement share → total-comp variant
  3. Regional multiplier (Praha, kraje) applied before band interpolation
"""

from functools import lru_cache

import pandas as pd

from cv_estimator.config import (
    APIFY_BLEND_WEIGHT,
    DATA_DIR,
    HIGH_SAMPLE_THRESHOLD,
    LOW_SAMPLE_THRESHOLD,
    SALARY_BAND_PCT_HIGH,
    SALARY_BAND_PCT_LOW,
    SALARY_CEILING,
    SALARY_FLOOR,
)
from cv_estimator.models import MarketPostings, SalaryEstimate
from cv_estimator.salary.region import resolve_region_multiplier

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


def _confidence_label(sample_n: float) -> str:
    if sample_n >= HIGH_SAMPLE_THRESHOLD:
        return "high"
    if sample_n >= LOW_SAMPLE_THRESHOLD:
        return "medium"
    return "low"


def _band_pct(confidence: str) -> float:
    return SALARY_BAND_PCT_LOW if confidence == "low" else SALARY_BAND_PCT_HIGH


def estimate_salary(
    cz_isco: str,
    seniority_score: int,
    *,
    role: str | None = None,
    region: str | None = None,
) -> SalaryEstimate:
    """Map (cz_isco, seniority_score 0-100) → SalaryEstimate range.

    `role` is the human-readable role string — only used to pick the
    IT vs non-IT regional multiplier column. `region` is a CZ NUTS code
    (CZ010..CZ080) or None for the national curve.
    """
    row = _lookup_row(cz_isco)
    p10 = int(row.get("p10", 0) or 0)
    p25 = int(row["p25"])
    p50 = int(row["p50"])
    p75 = int(row["p75"])
    p90 = int(row["p90"])
    mean = int(row.get("mean", 0) or 0)
    bonus_pct = float(row.get("bonus_pct", 0.0) or 0.0)
    supplement_pct = float(row.get("supplement_pct", 0.0) or 0.0)
    sample_n = float(row.get("sample_n", 0.0) or 0.0)

    confidence = _confidence_label(sample_n)
    band_pct = _band_pct(confidence)

    # Layer B — regional multiplier applied to ALL absolute amounts BEFORE
    # interpolation, so percentile_position still reflects national curve.
    mult, region_code = resolve_region_multiplier(region, role)
    if mult != 1.0:
        p10 = int(p10 * mult)
        p25 = int(p25 * mult)
        p50 = int(p50 * mult)
        p75 = int(p75 * mult)
        p90 = int(p90 * mult)
        mean = int(mean * mult)

    median, percentile = _interpolate(seniority_score, p25, p50, p75, p90)

    # Range = ±band_pct around interpolated median, clamped to (p25, p90).
    low = max(p25, int(median * (1 - band_pct)))
    high = min(p90, int(median * (1 + band_pct)))

    # Sanity clamp
    low = max(SALARY_FLOOR, low)
    high = min(SALARY_CEILING, high)
    median = max(low, min(high, median))

    # Total-comp = base × (1 + bonus + supplement). ISPV reports as % so divide.
    comp_mult = 1.0 + (bonus_pct / 100.0) + (supplement_pct / 100.0)
    total_comp_low = int(low * comp_mult)
    total_comp_median = int(median * comp_mult)
    total_comp_high = int(high * comp_mult)

    return SalaryEstimate(
        low=low,
        median=median,
        high=high,
        currency="CZK",
        percentile_position=percentile,
        market_p10=p10,
        market_p25=p25,
        market_p50=p50,
        market_p75=p75,
        market_p90=p90,
        market_mean=mean,
        bonus_pct=bonus_pct,
        supplement_pct=supplement_pct,
        total_comp_low=total_comp_low,
        total_comp_median=total_comp_median,
        total_comp_high=total_comp_high,
        sample_size=sample_n,
        confidence=confidence,
        region=region_code,
        region_multiplier=mult,
    )


def blend_with_postings(
    est: SalaryEstimate,
    postings: MarketPostings | None,
    *,
    weight: float = APIFY_BLEND_WEIGHT,
) -> SalaryEstimate:
    """Return a SalaryEstimate whose `median` (and low/high band, plus
    total_comp_*) has been nudged toward the live Apify median.

    ISPV stays the anchor (weight 1 - weight); the live signal nudges the
    point estimate toward present-day postings. No-op when postings is
    None or has no usable median.
    """
    if postings is None or postings.median is None:
        return est
    blended = int(est.median * (1 - weight) + postings.median * weight)
    # Recompute band around the new median, preserving the band-pct that
    # was already applied (low/high are still ±SALARY_BAND_PCT_* of est.median).
    if est.median > 0:
        ratio = blended / est.median
        new_low = max(SALARY_FLOOR, int(est.low * ratio))
        new_high = min(SALARY_CEILING, int(est.high * ratio))
    else:
        new_low, new_high = est.low, est.high
    new_low = min(new_low, blended)
    new_high = max(new_high, blended)

    # Total-comp scales with the same ratio so the relative bonus share holds.
    comp_mult = 1.0 + (est.bonus_pct + est.supplement_pct) / 100.0
    return est.model_copy(
        update={
            "low": new_low,
            "median": blended,
            "high": new_high,
            "total_comp_low": int(new_low * comp_mult),
            "total_comp_median": int(blended * comp_mult),
            "total_comp_high": int(new_high * comp_mult),
        }
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
