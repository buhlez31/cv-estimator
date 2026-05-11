#!/usr/bin/env python3
"""Preprocess raw MPSV / ISPV download → `data/ispv_<year>.csv`.

The ISPV portal (https://data.mpsv.cz/web/data/ispv-zamestnani) publishes
gross monthly earnings by CZ-ISCO classification with decile / quartile
breakdowns in JSON, JSON-LD, and JSON-schema form.

This script:
1. Reads `data/raw/ispv-zamestnani.json` (gitignored).
2. Filters to the MZDOVA sphere (private-sector wages — the canonical
   reference; PLATOVA = public-sector salaries, smaller sample for IT).
3. Emits ALL distinct CZ-ISCO codes in the MZDOVA sphere (not just IT).
   IT-only mapping previously here is preserved as a lookup label
   helper for the codes the pipeline cares about most.
4. Writes the table to `data/ispv_<year>.csv`.
"""

import json
import re
import sys

import pandas as pd

from cv_estimator.config import DATA_DIR, RAW_DATA_DIR

RAW_FILE = RAW_DATA_DIR / "ispv-zamestnani.json"

# Optional CZ-ISCO 4-digit → (English label, Czech label) for IT codes.
# For non-IT codes we emit "CZ-ISCO XXXX" as a placeholder label since
# the raw JSON doesn't carry a name field.
IT_ROLE_LABELS: dict[str, tuple[str, str]] = {
    "1330": ("ICT services manager", "Manažer v oblasti ICT"),
    "2511": ("Systems analyst", "Systémový analytik"),
    "2512": ("Software developer", "Vývojář software"),
    "2513": ("Web and multimedia developer", "Vývojář webu a multimédií"),
    "2514": ("Application programmer", "Aplikační programátor"),
    "2519": ("Software developer NEC", "Vývojář software jinde neuvedený"),
    "2521": ("Database designer/administrator", "Návrhář a správce databází"),
    "2522": ("Systems administrator", "Systémový administrátor"),
    "2523": ("Computer network professional", "Specialista počítačových sítí"),
    "2529": ("Database and network professional NEC", "Specialista DB a sítí jinde neuvedený"),
    "3511": ("ICT operations technician", "Technik provozu ICT"),
    "3512": ("ICT user support technician", "Technik uživatelské podpory ICT"),
    "3513": ("Computer network technician", "Technik počítačových sítí"),
    "3514": ("Web technician", "Webový technik"),
}


def _strip_isco_prefix(value: str) -> str:
    # "CzIsco/2512" → "2512"
    return value.rsplit("/", 1)[-1]


def _parse_year(period: str) -> int:
    # "rok 2025" → 2025
    m = re.search(r"(\d{4})", period)
    if not m:
        raise ValueError(f"Could not parse year from period {period!r}")
    return int(m.group(1))


def main() -> int:
    if not RAW_FILE.exists():
        print(
            f"Raw ISPV file not found at {RAW_FILE}.\n"
            "Download from https://data.mpsv.cz/web/data/ispv-zamestnani\n"
            "and place the JSON export as data/raw/ispv-zamestnani.json.",
            file=sys.stderr,
        )
        return 1

    with RAW_FILE.open(encoding="utf-8") as f:
        items = json.load(f)["polozky"]

    rows = []
    for it in items:
        # MZDOVA = private-sector wages; PLATOVA = public-sector salaries.
        # Use MZDOVA as the canonical reference (larger sample, market-rate).
        if it.get("sfera") != "MZDOVA":
            continue
        code = _strip_isco_prefix(it["czIsco"])
        label_en, label_cs = IT_ROLE_LABELS.get(code, (f"CZ-ISCO {code}", f"CZ-ISCO {code}"))
        rows.append(
            {
                "cz_isco_code": code,
                "role_label_en": label_en,
                "role_label_cs": label_cs,
                "p10": int(it.get("diferenciaceD1M", 0) or 0),
                "p25": int(it["diferenciaceQ1M"]),
                "p50": int(it["medianMzda"]),
                "p75": int(it["diferenciaceQ3M"]),
                "p90": int(it["diferenciaceD9M"]),
                "mean": int(it.get("mzdaPrumer", 0) or 0),
                # Percent of total monthly comp: ISPV reports as %, e.g. 28.8
                "bonus_pct": float(it.get("odmenaMzdy", 0) or 0),
                "supplement_pct": float(it.get("priplatekMzdy", 0) or 0),
                # Sample size in thousands of employees, e.g. 5.2 = 5 200
                "sample_n": float(it.get("pocetZamestnancuMzda", 0) or 0),
            }
        )

    if not rows:
        print("No MZDOVA rows found.", file=sys.stderr)
        return 2

    df = pd.DataFrame(rows).sort_values("cz_isco_code").reset_index(drop=True)
    year = _parse_year(items[0]["obdobi"])
    out_path = DATA_DIR / f"ispv_{year}.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
