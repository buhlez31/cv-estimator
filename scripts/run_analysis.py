#!/usr/bin/env python3
"""CLI entry point: `python scripts/run_analysis.py path/to/cv.pdf [--json]`.

Prints either a human-readable summary (default) or the raw JSON output.
Emits the buzzword baseline (objective, from explicit CV content) and the
hidden-assets-included track side-by-side. Only the inferred-capabilities
pass is evaluated skeptically — the baseline is the objective view.
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from cv_estimator.models import CVAnalysis, TrackResult
from cv_estimator.pipeline import analyze_cv
from cv_estimator.salary.role_mapping import UnmappedRoleError


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Analyze a CV file (PDF/DOCX).")
    parser.add_argument("cv_path", type=Path, help="Path to CV file")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON only")
    parser.add_argument(
        "--target-role",
        type=str,
        default=None,
        help='Target role title (e.g. "Senior Python Backend Engineer"). '
        "Anchors the whole analysis on this role and runs LLM #5 match "
        "assessment. When omitted, the auto-detected best-fit role is used.",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help='CZ NUTS region code (e.g. "CZ010" for Praha, "CZ080" for '
        "Moravskoslezský). Applies the ČSÚ regional multiplier to the ISPV "
        "national wage. Omit for the national curve.",
    )
    args = parser.parse_args()

    if not args.cv_path.exists():
        print(f"File not found: {args.cv_path}", file=sys.stderr)
        return 2

    file_bytes = args.cv_path.read_bytes()
    try:
        result = analyze_cv(
            file_bytes,
            args.cv_path.name,
            target_role=args.target_role,
            region=args.region,
        )
    except UnmappedRoleError as e:
        print(
            f"Role {e.role!r} did not match any CZ-ISCO entry in the ISPV "
            "database. Use a more standard job title (e.g. 'Senior Backend "
            "Engineer', 'Marketing Manager', 'Lawyer') or omit --target-role.",
            file=sys.stderr,
        )
        return 3

    if args.json:
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return 0

    _print_summary(result)
    return 0


def _print_summary(result: CVAnalysis) -> None:
    source_label = "target" if result.role_source == "target" else "auto-detected"
    print(
        f"Analyzed for role: {result.analysis_role} "
        f"(CZ-ISCO {result.cz_isco_code}, {source_label})"
    )
    if result.role_source == "target":
        print(f"Best-fit per CV: {result.detected_role}")
    print(f"Language: {result.language}")

    if result.target is not None:
        t = result.target
        print(f"\nMatch score vs {t.target_role}: {t.match_score}/100")
        print(f"  {t.rationale}")
        print("  Tip: pro analýzu best-fit role spusť bez --target-role na stejné CV.")

    market = result.track_explicit.salary_estimate
    region_note = (
        f" · region {market.region} (×{market.region_multiplier:.2f})"
        if market.region
        else " · national"
    )
    print(
        f"\nMarket band (P25-P90, ISPV "
        f"{result.processing_metadata.get('ispv_period', '?')}, "
        f"{result.processing_metadata.get('ispv_sphere', '?')}{region_note}): "
        f"{market.market_p25:,} – {market.market_p90:,} {market.currency} "
        f"(mean {market.market_mean:,}, sample n≈{int(market.sample_size * 1000)}, "
        f"confidence {market.confidence})"
    )

    _print_track("Buzzword baseline", result.track_explicit)
    _print_track("S hidden assets (potenciál)", result.track_with_inferred)

    mp = result.market_postings
    if mp is not None and mp.median is not None:
        print(
            f"\nLive jobs.cz postings (n={mp.sample_size} of {mp.total_postings}, "
            f"via Apify): P25 {mp.p25:,} | median {mp.median:,} | P75 {mp.p75:,} CZK"
        )
        if mp.sample_url:
            print(f"  Source: {mp.sample_url}")

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
    if s.bonus_pct + s.supplement_pct >= 1.0:
        print(
            f"  Total comp est. : {s.total_comp_low:,} – {s.total_comp_high:,} "
            f"{s.currency} (median {s.total_comp_median:,}, "
            f"bonus {s.bonus_pct:.1f}%, supp {s.supplement_pct:.1f}%)"
        )
    if s.platycz_position:
        print(f"  Refined via platy.cz: {s.platycz_position} ({s.platycz_url})")
    print(
        f"  Breakdown       : years {track.breakdown.years_experience:.0f} | "
        f"skills {track.breakdown.skills_depth:.0f} | "
        f"role {track.breakdown.role_progression:.0f} | "
        f"edu {track.breakdown.education:.0f}"
    )


if __name__ == "__main__":
    sys.exit(main())
