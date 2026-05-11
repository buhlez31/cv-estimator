# CV Estimator

AI case study. Reads CV (PDF/DOCX), estimates seniority score, predicts
market salary band from official Czech ISPV data, generates 3 concrete
recommendations for a +30 % salary uplift.

**Live:** [cv-estimator.streamlit.app](https://cv-estimator.streamlit.app)

## TL;DR

- **Pipeline.** Text extract → 4–5 LLM passes (explicit + inferred
  extraction, narrative, roadmap, optional target-role match) → 4-axis
  scoring → seniority aggregate → salary lookup.
- **Two parallel tracks.** Same CV scored twice: `track_explicit`
  (buzzword baseline) and `track_with_inferred` (adds hidden capabilities
  scoped to the role). The gap surfaces how much project-narrative
  signal the buzzword filter would miss.
- **Three-layer salary.** Layer A = official MPSV ISPV quantiles (296
  CZ-ISCO codes, mean, bonus share, confidence). Layer B = NUTS-3
  regional multipliers (CLI opt-in). Layer C = 513 platy.cz role-title
  rows blended 60/40 with ISPV when the matcher hits.
- **Cost / call.** 6 LLM calls without target role (~$0.045), 7 with
  target (~$0.055). All prompts ship as reviewer-visible `.md`
  artefacts in [`cv_estimator/prompts/`](cv_estimator/prompts/).
- **Output contract.** [`CVAnalysis`](cv_estimator/models.py) Pydantic
  schema, validated end-to-end. Pipeline is a thin orchestrator (no
  logic).

## Run

```bash
pip install -r requirements.txt && pip install -e .
streamlit run cv_estimator/ui/app.py
```

Needs `ANTHROPIC_API_KEY` in `.env` (copy from `.env.example`). CLI:

```bash
python scripts/run_analysis.py path/to/cv.pdf \
  [--target-role "Senior Backend Engineer"] [--region CZ010]
```

## Pipeline

```
analyze_cv(file_bytes, target_role=None, region=None)
    │
    ├── document.extract_text + detect_language (cs/en)
    │
    ├── LLM #1  extractors/explicit   → role, years, skills, education, field_of_study
    │
    ├── analysis_role = target_role or explicit.role
    │
    ├── LLM #2  extractors/inferred   → hidden capabilities scoped to analysis_role
    │                                   (skepticism, caveat, must/nice relevance)
    │
    ├── salary/role_mapping           → CZ-ISCO 4-digit code
    │                                   keyword rules → LLM fallback → UnmappedRoleError
    │
    ├── scoring/components            → ScoreBreakdown (0-100 per axis)
    │   ▶ years_experience            years / level-cap (junior 3, mid 10, senior 15, principal 20)
    │   ▶ skills_depth                LLM coverage scoring × 2 tracks
    │   ▶ role_progression            title keywords (analysis_role) + years
    │   ▶ education                   degree + prestige + role-aware field match
    │
    ├── scoring/seniority             weighted 30/35/20/15 → 0-100
    ├── salary/lookup                 SalaryEstimate per track (ISPV × region × platy.cz)
    │
    ├── LLM #3  explanation/narrative → strengths + gaps for analysis_role
    ├── LLM #4  explanation/roadmap   → 3 recommendations for +30 % uplift
    ├── LLM #5  explanation/match     → target-role fit (only when target supplied)
    │
    └── validation/sanity             → output-range invariants
                                  ▼
                           CVAnalysis (Pydantic)
```

All four ScoreBreakdown axes react to `analysis_role`: change the target
role and `years_experience` rebases against the new level cap,
`role_progression` keyword-matches the new title, `skills_depth` and
`education` re-score for the new domain.

## Salary layers

Every CZK in the output is traceable to a public source.

| Layer | Source | Granularity | Effect |
|---|---|---|---|
| A | MPSV ISPV ([open data](https://data.mpsv.cz/web/data/ispv-zamestnani)) | 296 CZ-ISCO occupational classes | P10/P25/P50/P75/P90 + mean + bonus share + sample-size confidence. Bucket interpolation: junior 0-40 → P25, mid 40-70 → P25→P50, senior 70-90 → P50→P75, principal 90+ → P75→P90. Low-n codes widen the output band to ±25 %. |
| B | ČSÚ regional wages | 14 NUTS-3 regions × {avg, IT} | Multiplier applied before bucket interpolation so percentile stays national; absolute CZK adjusts. Praha IT 1.30×, Ostrava 0.88×. CLI `--region CZ010`. |
| C | [platy.cz](https://www.platy.cz) | 513 specific role titles | Czech-aware token matcher with cross-language aliases (`developer ↔ vývojář`, `engineer ↔ inženýr`, `lawyer ↔ advokát`, exec abbreviations). Blends 60/40 with ISPV at the candidate's percentile. ISPV stays the dominant anchor; platy.cz refines for role specificity. No match → no-op. |

Total-comp variant (`base × (1 + bonus_pct + supplement_pct)`) and the
matched platy.cz position / URL surface on `SalaryEstimate` for
auditability.

## Two tracks + skepticism

- **`track_explicit`** — buzzword baseline. Coverage LLM scores only on
  literal CV skills. Objective view.
- **`track_with_inferred`** — same prompt + confident (`≥ 0.6`) inferred
  capabilities as supporting evidence. The model decides the lift.

Skepticism asymmetric by design:

| Where | Mechanism |
|---|---|
| Explicit baseline | Generics vs domain-specific filter inside the LLM prompt |
| Inferred extraction | Confidence anchored at 0.5, title-only inferences capped at 0.4, optional `caveat` field, second-order leaps rejected |
| Coverage scoring | Caveat-heavy or low-confidence passes get a 10–15 pt downgrade per `skills_coverage.md` rubric |

## Design choices

| Choice | Rationale |
|---|---|
| Heuristic scoring, not ML | Training on a handful of CVs is a red flag. Fixed-weight rubric is auditable. |
| Fixed weights 30/35/20/15 | Documented in [`config.py`](cv_estimator/config.py). Not tuned. |
| All-LLM skills coverage | Single mechanism for every role family. Skepticism handling in the prompt, not Python. |
| Pydantic everywhere | `CVAnalysis` is the single source of truth. LLM responses validated before downstream code touches them. |
| Pipeline = table of contents | Zero logic in `pipeline.py`; each module owns its slice. |
| Role mapping deterministic-first | Keyword rules in <1 ms; LLM fallback only on miss. Unmapped roles raise rather than silently default. |
| Three salary layers, not one | ISPV anchors the official curve; region adjusts geography; platy.cz refines role specificity. Each layer cites a public source. |

## Repo layout

```
cv_estimator/
├── pipeline.py           # thin orchestrator
├── models.py             # Pydantic contract (CVAnalysis, SalaryEstimate, …)
├── config.py             # weights, constants
├── llm.py                # Anthropic client + prompt loader
├── extractors/           # PDF/DOCX text + LLM #1 / #2
├── scoring/              # 4-axis breakdown + weighted aggregate
├── salary/               # CZ-ISCO mapping + ISPV lookup + region + platy.cz
├── explanation/          # narrative + roadmap + match LLM passes
├── validation/           # output sanity checks
├── prompts/              # 7 .md prompt artefacts
├── data/                 # ispv_2025.csv, platycz_2025.csv, regional_multipliers_2025.csv
└── ui/app.py             # Streamlit
tests/                    # 92 tests, no network — LLM calls patched
scripts/                  # CLI + data ingest
```

## Tests

```bash
pytest -q   # 92 tests, no network — LLM calls patched in e2e tests
```

## License

MIT — see [LICENSE](LICENSE).
