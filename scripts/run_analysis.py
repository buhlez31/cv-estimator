#!/usr/bin/env python3
"""CLI entry point: `python scripts/run_analysis.py path/to/cv.pdf [--json]`.

Prints either a human-readable summary (default) or the raw JSON output.
After Branch A: emits both the skeptical baseline and the hidden-assets
track side-by-side.
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from cv_estimator.models import CVAnalysis, TrackResult
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

    _print_summary(result)
    return 0


def _print_summary(result: CVAnalysis) -> None:
    print(f"Role: {result.detected_role} (CZ-ISCO {result.cz_isco_code})")
    print(f"Language: {result.language}")

    market = result.track_explicit.salary_estimate
    print(
        f"\nMarket band (P25-P90, ISPV "
        f"{result.processing_metadata.get('ispv_period', '?')}, "
        f"{result.processing_metadata.get('ispv_sphere', '?')}): "
        f"{market.market_p25:,} – {market.market_p90:,} {market.currency}"
    )

    _print_track("Buzzword baseline (skeptický)", result.track_explicit)
    _print_track("S hidden assets (potenciál)", result.track_with_inferred)

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


def _print_track(label: str, track: TrackResult) -> None:
    s = track.salary_estimate
    print(f"\n{label}")
    print(f"  Seniority score : {track.seniority_score}/100")
    print(
        f"  Salary estimate : {s.low:,} – {s.high:,} {s.currency} "
        f"(median {s.median:,}, P{s.percentile_position})"
    )
    print(
        f"  Breakdown       : years {track.breakdown.years_experience:.0f} | "
        f"skills {track.breakdown.skills_depth:.0f} | "
        f"role {track.breakdown.role_progression:.0f} | "
        f"edu {track.breakdown.education:.0f}"
    )


if __name__ == "__main__":
    sys.exit(main())
