"""Regional wage multipliers (Layer B of salary computation).

Loaded from `cv_estimator/data/regional_multipliers_2025.csv`. Tech roles
get a slightly higher multiplier in Praha + Brno (ČSÚ regional data
shows IT compresses geographic spread less than blue-collar work).
"""

from functools import lru_cache

import pandas as pd

from cv_estimator.config import REGIONAL_MULTIPLIERS_PATH


@lru_cache(maxsize=1)
def _load_multipliers() -> pd.DataFrame:
    df = pd.read_csv(REGIONAL_MULTIPLIERS_PATH, dtype={"region_code": str})
    df = df.set_index("region_code")
    return df


def list_regions() -> list[tuple[str, str]]:
    """Return [(code, label), ...] for UI dropdown. Adds a leading
    national option that the caller can render as the default."""
    df = _load_multipliers()
    return [(code, str(row["region_label"])) for code, row in df.iterrows()]


def _is_tech_role(role: str | None) -> bool:
    """Lightweight role-family check — duplicates the keyword logic in
    scoring/components but stays local to avoid a cyclic import. The IT
    multiplier kicks in for any engineering / dev / data / analyst /
    architect title."""
    if not role:
        return False
    low = role.lower()
    return any(
        kw in low
        for kw in (
            "engineer",
            "developer",
            "programmer",
            "scientist",
            "analyst",
            "architect",
            "devops",
            "sre",
            "data ",
            "ml ",
            "ai ",
            "ai/",
            "vývojář",
            "programátor",
            "technik",
        )
    )


def resolve_region_multiplier(region: str | None, role: str | None) -> tuple[float, str | None]:
    """Pick the right multiplier column based on role family.

    Returns (multiplier, normalised_region_code). Multiplier is 1.0 when
    `region` is None or unknown. `normalised_region_code` is None when
    no region was applied (callers can render "Národní průměr").
    """
    if not region:
        return 1.0, None
    df = _load_multipliers()
    if region not in df.index:
        return 1.0, None
    row = df.loc[region]
    column = "multiplier_it" if _is_tech_role(role) else "multiplier_avg"
    return float(row[column]), region
