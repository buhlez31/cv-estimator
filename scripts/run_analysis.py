#!/usr/bin/env python3
"""CLI entry point: `python scripts/run_analysis.py path/to/cv.pdf [--json]`.

Prints either a human-readable summary (default) or the raw JSON output.
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from cv_estimator.pipeline import analyze_cv


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Analyze a CV file (PDF/DOCX).")
    parser.add_argument("cv_path", type=Path, help="Path to CV file")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON only")
    args = parser.parse_args()

    if not args.cv_path.exists():
        print(f"File not found: {args.cv_path}", file=sys.stderr)
        return 2

    file_bytes = args.cv_path.read_bytes()
    result = analyze_cv(file_bytes, args.cv_path.name)

    if args.json:
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return 0

    print(f"Role: {result.detected_role} (CZ-ISCO {result.cz_isco_code})")
    print(f"Language: {result.language}")
    print(f"Seniority score: {result.seniority_score}/100")
    print(
        f"Salary estimate: {result.salary_estimate.low:,} – "
        f"{result.salary_estimate.high:,} {result.salary_estimate.currency} "
        f"(median {result.salary_estimate.median:,}, P{result.salary_estimate.percentile_position})"
    )
    print("\nBreakdown:")
    print(f"  Years experience : {result.breakdown.years_experience:.0f}")
    print(f"  Skills depth     : {result.breakdown.skills_depth:.0f}")
    print(f"  Role progression : {result.breakdown.role_progression:.0f}")
    print(f"  Education        : {result.breakdown.education:.0f}")

    print("\nStrengths:")
    for s in result.strengths:
        print(f"  + {s}")
    print("\nGaps:")
    for g in result.gaps:
        print(f"  - {g}")
    print("\nRecommendations:")
    for i, r in enumerate(result.recommendations, start=1):
        print(f"  {i}. [{r.target_skill} | {r.time_investment}] {r.action}")
        print(f"     Impact: {r.expected_impact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
