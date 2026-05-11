#!/usr/bin/env python3
"""Preprocess raw platy.cz xlsx → `cv_estimator/data/platycz_2025.csv`.

Source: `data/platy_salaries.xlsx` (user-provided dump from platy.cz —
gitignored, treated as raw input). Output ships inside the package via
the `data/*.csv` package-data glob so it deploys to Streamlit Cloud.

Pattern mirrors `scripts/prepare_ispv_data.py`: drop demographic noise
and rows without quantiles, write a tight CSV the runtime can lru_cache.
"""

import sys
from pathlib import Path

import pandas as pd

from cv_estimator.config import DATA_DIR, REPO_ROOT

RAW_FILE: Path = REPO_ROOT / "data" / "platy_salaries.xlsx"


def main() -> int:
    if not RAW_FILE.exists():
        print(
            f"Raw platy.cz xlsx not found at {RAW_FILE}.\n"
            "Drop the platy_salaries.xlsx export into the data/ directory and rerun.",
            file=sys.stderr,
        )
        return 1

    df = pd.read_excel(RAW_FILE, sheet_name="Positions")
    df = df.dropna(subset=["10th percentile (CZK)", "90th percentile (CZK)"])
    df = df[df["Currency"] == "CZK"]

    p10 = df["10th percentile (CZK)"].astype(int)
    p90 = df["90th percentile (CZK)"].astype(int)
    out = pd.DataFrame(
        {
            "category_slug": df["Category slug"],
            "position_slug": df["Position slug"],
            "position_label": df["Position"],
            "p10": p10,
            "p90": p90,
            "median_proxy": ((p10 + p90) / 2).astype(int),
            "url": df["URL"],
        }
    )
    out = out.sort_values(["category_slug", "position_slug"]).reset_index(drop=True)

    out_path = DATA_DIR / "platycz_2025.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {len(out)} rows → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
