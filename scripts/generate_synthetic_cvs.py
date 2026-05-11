#!/usr/bin/env python3
"""Generate synthetic CV fixtures via Claude for testing the pipeline.

Outputs to `tests/fixtures/synthetic_cvs/` as .txt files (parsed via the .txt
branch of document.extract_text). Each profile gets a buzzword-heavy variant
(suffix `_A.txt`) and an implicit/outcome variant (suffix `_B.txt`) — used by
the A/B hidden-assets test described in the brief.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

from cv_estimator import llm

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "synthetic_cvs"

PROFILES = [
    ("junior_dev_cs", "cs", "junior", "backend developer"),
    ("mid_data_en", "en", "mid", "data scientist"),
    ("senior_pe_en", "en", "senior", "platform engineer"),
    ("principal_ml_cs", "cs", "principal", "machine learning engineer"),
    ("ab_test_subject", "en", "senior", "data engineer"),
]

PROMPT = """Write two short CVs (~250-400 words each) for the same fictional person.

Person: {seniority} {role}, language: {language}.

VARIANT A (buzzword-heavy): packed with skill keywords listed as bullets
(technologies, tools, methodologies). Explicit, scannable, light on outcomes.

VARIANT B (implicit/outcome-driven): same person, but describe what they
*did* — projects, responsibilities, quantified results — and minimize the
buzzword section. Same underlying skills must be inferable from project
descriptions.

Return strict JSON:
{{
  "variant_a": "<full CV text>",
  "variant_b": "<full CV text>"
}}
"""


def main() -> int:
    load_dotenv()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for slug, lang, seniority, role in PROFILES:
        print(f"Generating {slug} ({seniority} {role}, {lang}) …")
        result = llm.call_json(PROMPT.format(seniority=seniority, role=role, language=lang))
        (OUTPUT_DIR / f"{slug}_A.txt").write_text(result["variant_a"], encoding="utf-8")
        (OUTPUT_DIR / f"{slug}_B.txt").write_text(result["variant_b"], encoding="utf-8")
    print(f"\nWrote {len(PROFILES) * 2} CVs to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
