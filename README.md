# CV Estimator

AI case study. Reads CV (PDF/DOCX), estimates seniority score, predicts
market salary band from official Czech ISPV data, generates 3
recommendations for +30 % uplift.

Live: [cv-estimator.streamlit.app](https://cv-estimator.streamlit.app)

## Run

```bash
pip install -r requirements.txt && pip install -e .
streamlit run cv_estimator/ui/app.py
```

Needs `ANTHROPIC_API_KEY` in `.env` (copy from `.env.example`). CLI mode:
`python scripts/run_analysis.py path/to/cv.pdf [--target-role "Senior Backend Engineer"]`.

## Pipeline

```
analyze_cv(file_bytes, target_role=None)
    │
    ├── document.extract_text + detect_language (cs/en)
    │
    ├── LLM #1  extractors/explicit   → role, years, skills, education, field_of_study
    │
    ├── analysis_role = target_role or explicit.role
    │
    ├── LLM #2  extractors/inferred   → hidden capabilities scoped to analysis_role
    │                                   (skepticism + caveat + must/nice relevance)
    │
    ├── salary/role_mapping           → CZ-ISCO 4-digit code
    │                                   (keyword rules → LLM fallback → UnmappedRoleError)
    │
    ├── scoring/components            → ScoreBreakdown (4 axes, 0-100)
    │   ▶ years_experience            years/15 × 100
    │   ▶ skills_depth                LLM coverage scoring × 2 tracks
    │   ▶ role_progression            title keywords + years
    │   ▶ education                   degree + prestige + role-aware field match
    │
    ├── scoring/seniority             weighted 30/35/20/15 → 0-100
    ├── salary/lookup                 SalaryEstimate per track
    │
    ├── LLM #3  explanation/narrative → strengths + gaps
    ├── LLM #4  explanation/roadmap   → 3 recommendations
    ├── LLM #5  explanation/match     → target-role fit (only with target_role)
    │
    └── validation/sanity             → output-range invariants
                                  ▼
                           CVAnalysis (Pydantic)
```

**Two parallel tracks.** Every analysis emits `track_explicit` (buzzword
baseline — what CV literally says) and `track_with_inferred` (adds
inferred caps with confidence ≥ 0.6 as evidence to the LLM coverage
scorer). The gap measures how much the candidate's description style
under-represents them.

**Cost.** 6 LLM calls without target role (~$0.045), 7 with target
(~$0.055). Prompts live in [`cv_estimator/prompts/*.md`](cv_estimator/prompts/)
as reviewer-visible artefacts. Output contract:
[`cv_estimator/models.py`](cv_estimator/models.py).

## Data approach

**Source: MPSV ISPV open data** — [data.mpsv.cz/web/data/ispv-zamestnani](https://data.mpsv.cz/web/data/ispv-zamestnani).
Official Czech earnings statistics published by the Ministry of Labour
and Social Affairs. Quantiles P25 / P50 / P75 / P90 per CZ-ISCO
occupation code. Same dataset ČSÚ uses for pension valorization —
defensible, free, no scraping.

[`cv_estimator/data/ispv_2025.csv`](cv_estimator/data/ispv_2025.csv) is
generated from the official MPSV JSON export (period `rok 2025`, sphere
`MZDOVA` — private-sector wages, where almost all professional
employment sits). 296 CZ-ISCO codes covered. Regenerate via
[`scripts/prepare_ispv_data.py`](scripts/prepare_ispv_data.py); drop the
raw JSON download into `data/raw/` and run the script.

**Role → CZ-ISCO mapping.** Priority-ranked keyword rules in
[`cv_estimator/salary/role_mapping.py`](cv_estimator/salary/role_mapping.py)
— deterministic, < 1 ms, free. Unknown titles fall through to an LLM
fallback (passes the role string + the 296 known codes + ISCO-08 family
hints). Roles that survive both layers raise `UnmappedRoleError` rather
than silently picking a default.

**Score → salary mapping.** Bucketed interpolation onto the ISPV quantile
curve: junior 0-40 → P25, mid 40-70 → P25-P50, senior 70-90 → P50-P75,
principal 90+ → P75-P90. Output range ±15 % around the interpolated
median, clamped to (P25, P90).

## Design choices

| Choice | Rationale |
|---|---|
| Heuristic scoring, not ML | Training on a handful of CVs is a red flag. Fixed-weight rubric is auditable. |
| Fixed weights 30/35/20/15 | Documented in [`config.py`](cv_estimator/config.py). Not tuned. |
| All-LLM skills coverage | Single mechanism for every role family. Skepticism / overclaim handling lives in the prompt, not Python. |
| Pydantic everywhere | `CVAnalysis` is the single source of truth. LLM responses validated before downstream code touches them. |
| Pipeline = table of contents | Zero logic in `pipeline.py`; each module owns its slice. |

## Tests

```bash
pytest -q   # 78 tests, no network — LLM calls patched in e2e tests
```

## Deploy (Streamlit Community Cloud)

1. [share.streamlit.io](https://share.streamlit.io) → New app →
   repo, branch `main`, main file `cv_estimator/ui/app.py`.
2. Advanced settings → Secrets:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
3. Deploy. Auto-redeploys on every push to `main`.

Uploaded CV stays in Streamlit server RAM only — never written to disk.
Anthropic logs API calls per their commercial data policy (30-day
retention, no training on API content). Owner's key bills owner's
account for every visitor.

## License

MIT — see [LICENSE](LICENSE).
