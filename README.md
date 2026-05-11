# CV Estimator

> AI case-study system that reads a CV (PDF / DOCX), estimates the candidate's
> seniority score, predicts a market salary range from official Czech ISPV
> data, and generates 3 concrete recommendations for a +30 % salary uplift.

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate

pip install -r requirements-dev.txt
pip install -e .

cp .env.example .env  # add ANTHROPIC_API_KEY=...

pre-commit install    # optional, format-on-commit
```

## Run

```bash
# Web UI (recommended)
streamlit run cv_estimator/ui/app.py

# CLI
python scripts/run_analysis.py path/to/cv.pdf
python scripts/run_analysis.py path/to/cv.pdf --json
```

## Pipeline

```
        ┌──────────────────────────────────────────────┐
        │  pipeline.analyze_cv(file_bytes, filename)   │
        └──────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
 document.extract_text  → raw_text → detect_language (cs / en)
        │
        ├── LLM #1  extractors/explicit.py  →  role, years, skills, education
        ├── LLM #2  extractors/inferred.py  →  inferred_capabilities (hidden assets)
        │
        ├── salary/role_mapping.py          →  CZ-ISCO 4-digit code
        ├── scoring/components.py           →  ScoreBreakdown (4 components, 0-100 each)
        ├── scoring/seniority.py            →  weighted aggregate score (0-100)
        ├── salary/lookup.py                →  SalaryEstimate from ISPV quantiles
        │
        ├── LLM #3  explanation/narrative.py →  strengths + gaps (3-5 each, language-aware)
        ├── LLM #4  explanation/roadmap.py   →  exactly 3 recommendations
        │
        └── validation/sanity.py             →  output-range invariants
                              │
                              ▼
                       CVAnalysis (Pydantic)
```

Four LLM calls, each driven by a prompt loaded from
`cv_estimator/prompts/*.md` (kept as artifacts, not Python strings).
The output schema in [`cv_estimator/models.py`](cv_estimator/models.py) is the
contract that every module builds around — *output-first design*.

## Data approach

**Salary source: MPSV ISPV open data** — [data.mpsv.cz/web/data/ispv-zamestnani](https://data.mpsv.cz/web/data/ispv-zamestnani).

Official Czech earnings statistics, published by the Ministry of Labour and
Social Affairs with quantiles (P25 / P50 / P75 / P90) per CZ-ISCO occupation
code. Used by ČSÚ for pension valorization — defensible, free, no scraping.

The committed [`data/ispv_2024.csv`](data/ispv_2024.csv) is a 14-row snapshot
filtered to IT-relevant CZ-ISCO codes (251x developers, 252x DB / network,
1330 ICT managers, 351x technicians). The preprocessing path is exposed via
[`scripts/prepare_ispv_data.py`](scripts/prepare_ispv_data.py) so the table
can be regenerated when MPSV publishes new figures.

**Role → CZ-ISCO mapping** ([`cv_estimator/salary/role_mapping.py`](cv_estimator/salary/role_mapping.py))
is a priority-ranked keyword rule table — deterministic, testable, no LLM
cost. Trade-off discussed below.

**Score → percentile interpolation** ([`cv_estimator/salary/lookup.py`](cv_estimator/salary/lookup.py))
anchors the seniority score 0-100 onto the ISPV quantile curve: 25→P25,
50→P50, 75→P75, 90→P90, linear in between. The output range is ±15 % around
the interpolated median, clamped to (P25, P90).

## Trade-offs & design decisions

| Choice | Rationale |
|---|---|
| **Heuristic scoring, not ML** | Training a model on a handful of CVs is a red flag for any reviewer. A fixed-weight rubric is auditable and explains its output. |
| **Fixed weights 30 / 35 / 20 / 15** | Encoded in [`config.py`](cv_estimator/config.py) (`WEIGHT_YEARS`, `WEIGHT_SKILLS`, `WEIGHT_ROLE`, `WEIGHT_EDUCATION`). Documented, not tuned. |
| **4 LLM calls, not 1 big one** | Two-pass extraction (explicit + inferred) is the product's key differentiator. Keeping each call narrow improves JSON adherence and lets each prompt iterate independently. |
| **Prompts as `.md` files** | Reviewer-visible artefacts. No escaping. Templates filled by `str.replace`, not `str.format`, so JSON braces in the prompt body don't need escaping. |
| **Role mapping: keyword rules, not LLM** | Deterministic, < 1 ms, no API cost on a code that gets called every run. Misses fall back to `2519` (SW dev NEC) which has sensible default ISPV figures. |
| **Pydantic everywhere** | `CVAnalysis` is the contract. Every LLM response is validated against a typed model before downstream code touches it — pipeline fails fast on malformed JSON instead of carrying it. |
| **No Sphinx, Airflow, Docker, CI** | Within 6–12 h budget. Brief explicitly says *"rather simpler but functional"*. |
| **No scraping** | ISPV open data has a CSV download. Legal-clean. |

## The hidden-assets thesis

The product differentiator is `inferred_capabilities` ([extractors/inferred.py](cv_estimator/extractors/inferred.py)):
a second LLM pass that finds skills *implied* by project descriptions
("automated weekly reporting for 200 stakeholders" → `python`, `sql`,
`stakeholder management`) instead of the buzzword list at the bottom of the
CV.

**A/B buzzword test** ([`scripts/generate_synthetic_cvs.py`](scripts/generate_synthetic_cvs.py))
produces two CVs for the same fictional candidate:

- **Variant A** — buzzword-heavy: bullet list of technologies and methods.
- **Variant B** — outcome-driven: same person, same skills, but described
  as *what they did* and *what they delivered* (with metrics).

Expected: A and B land within roughly the same band. If A scores
significantly higher, the inferred pass is failing and the prompt needs
work. This is the kind of test the standard buzzword-matching CV screeners
fail by design — and the reason the second LLM pass is worth its latency.

## Architecture invariants

- `cv_estimator/models.py` is the only place output shapes are defined.
  Every other module accepts and produces these types.
- `cv_estimator/pipeline.py` is a table of contents. **No logic** —
  just a sequence of module calls in the order shown in the diagram above.
- `cv_estimator/llm.py` is the only module that talks to Anthropic.
- Every LLM-using module imports `from cv_estimator import llm` and calls
  `llm.call_json(...)` so it can be mocked in one place
  ([tests/test_pipeline_e2e.py](tests/test_pipeline_e2e.py)).

## Tests

```bash
pytest -q
```

29 tests, no network access required — the end-to-end test patches
`cv_estimator.llm.call_json` with deterministic JSON fixtures.

## Layout

```
cv_estimator/                 # main package — imported via `pip install -e .`
├── models.py                 # Pydantic schemas — single source of truth
├── pipeline.py               # thin orchestrator
├── config.py                 # weights, constants, CZ-ISCO prefixes
├── llm.py                    # Anthropic client + prompt loader
├── extractors/               # PDF/DOCX text + explicit/inferred LLM passes
├── scoring/                  # 4-component breakdown + weighted aggregate
├── salary/                   # role → CZ-ISCO + ISPV lookup
├── explanation/              # narrative + roadmap LLM passes
├── validation/               # output sanity checks
├── prompts/                  # 4 LLM prompts as .md artefacts
└── ui/app.py                 # Streamlit
data/ispv_2024.csv            # preprocessed ISPV snapshot
tests/                        # pytest suite + fixtures
scripts/                      # CLI entry points
```

## License

MIT — see [LICENSE](LICENSE).
