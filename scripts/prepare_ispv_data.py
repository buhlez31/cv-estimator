#!/usr/bin/env python3
"""Preprocess raw MPSV / ISPV download → `data/ispv_2024.csv`.

The ISPV portal (https://data.mpsv.cz/web/data/ispv-zamestnani) publishes
gross monthly earnings by CZ-ISCO classification with P10/P25/P50/P75/P90
quantiles. Their raw export is a wide Excel sheet with all professions.

This script:
1. Reads `data/raw/ispv_*.xlsx` (or `.csv`) — gitignored.
2. Filters to IT CZ-ISCO codes (prefixes 251x, 252x, 1330, 351x).
3. Writes the slim 8-column lookup table to `data/ispv_2024.csv`.

If no raw file is present, prints instructions and exits.
"""

import sys

import pandas as pd

from cv_estimator.config import DATA_DIR, IT_ISCO_PREFIXES

RAW_DIR = DATA_DIR / "raw"
OUTPUT = DATA_DIR / "ispv_2024.csv"


def main() -> int:
    raw_files = sorted(RAW_DIR.glob("ispv_*.xlsx")) + sorted(RAW_DIR.glob("ispv_*.csv"))
    if not raw_files:
        print(
            "No raw ISPV file found in data/raw/.\n"
            "Download from https://data.mpsv.cz/web/data/ispv-zamestnani\n"
            "and place as data/raw/ispv_<year>.xlsx (or .csv).\n"
            "The committed data/ispv_2024.csv is a pre-built snapshot."
        )
        return 1

    src = raw_files[-1]
    print(f"Reading {src} …")
    df = pd.read_excel(src) if src.suffix == ".xlsx" else pd.read_csv(src)

    # Expected columns (adapt as needed for the actual ISPV export schema):
    # KZAM_kod (CZ-ISCO code), KZAM_nazev (role name), P25, P50, P75, P90
    df.columns = [c.lower() for c in df.columns]
    code_col = next((c for c in df.columns if "kzam_kod" in c or "isco" in c), None)
    name_col = next((c for c in df.columns if "kzam_nazev" in c or "nazev" in c), None)
    if not code_col or not name_col:
        print(f"Unexpected schema. Columns: {list(df.columns)}", file=sys.stderr)
        return 2

    df[code_col] = df[code_col].astype(str)
    mask = df[code_col].str.startswith(IT_ISCO_PREFIXES)
    sub = df.loc[mask, [code_col, name_col, "p25", "p50", "p75", "p90"]].copy()
    sub.columns = ["cz_isco_code", "role_label_cs", "p25", "p50", "p75", "p90"]
    sub.insert(1, "role_label_en", sub["role_label_cs"])  # placeholder, fill manually

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(sub)} rows → {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
