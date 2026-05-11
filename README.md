# CV Estimator

> AI case-study system. Reads a CV (PDF / DOCX), estimates seniority score,
> predicts market salary band from official Czech ISPV data, generates 3
> recommendations for a +30 % salary uplift.

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
# Web UI
streamlit run cv_estimator/ui/app.py

# CLI
python scripts/run_analysis.py path/to/cv.pdf
python scripts/run_analysis.py path/to/cv.pdf --target-role "Senior Python Backend Engineer"
```

If `--target-role` is supplied, the **entire analysis** anchors on that role:
CZ-ISCO lookup, salary band, hidden-asset scoping, plus a 5th LLM call that
scores how well the CV fits the target. When empty, the auto-detected role
from the CV drives everything.

## Deploy (Streamlit Community Cloud)

1. Push repo to GitHub (already at `buhlez31/cv-estimator`).
2. [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub →
   **New app** → pick repo, branch `main`, main file `cv_estimator/ui/app.py`.
3. **Advanced settings → Secrets**:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Deploy. Build ~3-5 min. URL: `https://<app-name>.streamlit.app`.

Python pinned via [`runtime.txt`](runtime.txt). Runtime deps in
[`requirements.txt`](requirements.txt); dev tooling in
[`requirements-dev.txt`](requirements-dev.txt).

**Data flow on deploy.** Uploaded CV stays in Streamlit server RAM
(BytesIO buffer) — never written to disk. Extracted text is sent to the
Anthropic API per call. Anthropic logs API calls per their commercial
data policy (30-day retention by default, no training on API content).
The deployed app uses the owner's `ANTHROPIC_API_KEY`: every visitor's
analysis bills the owner's account. Set a monthly budget cap in the
Anthropic console; gate access via Streamlit Cloud's "Viewer auth" if
you want only invited testers.

## Pipeline

```
pipeline.analyze_cv(file_bytes, target_role=None)
    │
    ├── document.extract_text + detect_language (cs / en)
    │
    ├── LLM #1  extractors/explicit   → role, years, skills, education,
    │                                   field_of_study
    │
    ├── analysis_role = target_role or explicit.role
    │
    ├── LLM #2  extractors/inferred   → hidden capabilities scoped to
    │                                   analysis_role, with confidence
    │                                   + caveat + must/nice relevance
    │
    ├── salary/role_mapping           → CZ-ISCO 4-digit code
    │                                   (keyword rules → LLM fallback →
    │                                    UnmappedRoleError if no match)
    │
    ├── scoring/components            → 4-axis ScoreBreakdown (0-100)
    │   ▶ years_experience            years / 15 × 100
    │   ▶ skills_depth                LLM coverage scoring × 2 tracks
    │                                 (`skills_coverage` prompt)
    │   ▶ role_progression            title keywords + years
    │   ▶ education                   degree + prestige + role-aware
    │                                 field-relevance modifier
    │
    ├── scoring/seniority             weighted 30/35/20/15 → 0-100
    ├── salary/lookup                 SalaryEstimate per track
    │                                 (junior/mid/senior/principal buckets)
    │
    ├── LLM #3  explanation/narrative → strengths + gaps
    ├── LLM #4  explanation/roadmap   → 3 recommendations
    ├── LLM #5  explanation/match     → target-role fit score (only with target)
    │
    └── validation/sanity             → output-range invariants
                                  ▼
                           CVAnalysis (Pydantic)
```

**LLM cost per analysis:** 6 calls (no target) ~$0.045 — 7 calls (with target)
~$0.055. Plus a conditional fallback for `role_mapping` on unknown titles
(~$0.003).

Prompts live in `cv_estimator/prompts/*.md` as reviewer-visible artefacts.
The output contract is [`cv_estimator/models.py`](cv_estimator/models.py).

## Data

**Salary source: MPSV ISPV open data** — [data.mpsv.cz/web/data/ispv-zamestnani](https://data.mpsv.cz/web/data/ispv-zamestnani).
Official Czech earnings statistics, quantiles (P25 / P50 / P75 / P90) per
CZ-ISCO occupation code. Used by ČSÚ for pension valorization.

[`data/ispv_2025.csv`](data/ispv_2025.csv) is generated from the official
MPSV JSON (period `rok 2025`, sphere `MZDOVA` — private-sector wages).
Regenerate via [`scripts/prepare_ispv_data.py`](scripts/prepare_ispv_data.py).

**Role → CZ-ISCO**: priority-ranked keyword rules with an LLM fallback
across 296 codes. Deterministic, testable. Unknown titles surface as
`UnmappedRoleError` rather than silently defaulting.

**Score → percentile**: bucketed interpolation onto the ISPV quantile
curve (junior 0-40 → P25, mid 40-70 → P25-P50, senior 70-90 → P50-P75,
principal 90+ → P75-P90). Output range ±15 % around the interpolated
median, clamped to (P25, P90).

## Design choices

| Choice | Rationale |
|---|---|
| **Heuristic scoring, not ML** | Training on a handful of CVs is a red flag. Fixed-weight rubric is auditable. |
| **Fixed weights 30 / 35 / 20 / 15** | Documented in [`config.py`](cv_estimator/config.py). Not tuned. |
| **Output-first: Pydantic contract** | `CVAnalysis` is the single source of truth. LLM responses validated before downstream code touches them. |
| **Prompts as `.md` files** | Reviewer-visible. Filled by `str.replace`, no escaping needed. |
| **All-LLM skills coverage** | Single mechanism for every role family (tech, business, marketing, legal, etc.). Skepticism / overclaim handling lives in the prompt, not Python. |
| **Pipeline = table of contents** | Zero logic in `pipeline.py`; each module owns its slice. |

## Hidden-assets thesis

The product differentiator is `inferred_capabilities`: a second LLM pass
that finds skills *implied* by project descriptions ("automated weekly
reporting for 200 stakeholders" → `python`, `sql`, `stakeholder
management`) instead of the buzzword list at the bottom of the CV.

### Two parallel tracks

The pipeline emits **two independent scoring tracks** so the reader sees
buzzword vs hidden-assets analyses side-by-side:

- **`track_explicit`** — buzzword baseline. LLM coverage_percent from
  literal CV content only.
- **`track_with_inferred`** — same prompt, plus inferred caps with
  `confidence ≥ 0.6` as supporting evidence. The model decides how much
  they lift the score, per its rubric.

When the two coincide, that itself is a signal — nothing for the inferred
pass to surface. When they diverge, the gap measures how much the
candidate's description style under-represents them.

### Skepticism

Applied asymmetrically:
- **Explicit baseline**: skepticism limited to "are these domain-specific
  or generic fluff?" Generic skills don't count toward coverage.
- **Inferred pass** ([`extract_inferred.md`](cv_estimator/prompts/extract_inferred.md)):
  full skepticism protocol — confidence anchored at 0.5 by default,
  title-only inferences capped at 0.4, optional `caveat` field on
  team-scope or peak-metric ambiguity, second-order leaps rejected.
- **Coverage scoring** ([`skills_coverage.md`](cv_estimator/prompts/skills_coverage.md)):
  caveat-heavy or low-confidence inferred passes get a 10–15 point
  downgrade per the prompt's rubric.

The UI renders each `caveat` in italics under the evidence quote so the
reader can discount accordingly.

### Education: role-aware field relevance

`_education_score` factors the candidate's `field_of_study` against the
analysis role's family.

| Degree | Base | Modifier | Effect |
|---|---|---|---|
| none | 0 | — | always 0 |
| high_school | 10 | match | +5 |
| bachelor | 30 | adjacent | 0 |
| master | 50 | mismatch | −25 |
| phd | 70 | empty field | base × 0.5 |

Plus +5 prestige bonus for institutions in `PRESTIGE_INSTITUTION_KEYWORDS`
(ČVUT, MIT, Oxford, Charles University, etc.).

Examples (ČVUT prestige applied):
- Master CS + Senior Backend Engineer (match) → 50 + 5 + 5 = **60**
- Master History + Senior Backend Engineer (mismatch) → 50 + 5 − 25 = **30**
- No degree listed → **0** regardless of anything else

## Tests

```bash
pytest -q
```

78 tests, no network — `cv_estimator.llm.call_json` is patched with
deterministic JSON in the e2e tests.

## Layout

```
cv_estimator/
├── models.py        # Pydantic schemas — single source of truth
├── pipeline.py      # thin orchestrator
├── config.py        # weights, constants, CZ-ISCO prefixes
├── llm.py           # Anthropic client + prompt loader
├── extractors/      # PDF/DOCX text + explicit/inferred LLM passes
├── scoring/         # 4-component breakdown + weighted aggregate
├── salary/          # role → CZ-ISCO + ISPV lookup
├── explanation/     # narrative + roadmap + match LLM passes
├── validation/      # output sanity checks
├── prompts/         # LLM prompts as .md artefacts
└── ui/app.py        # Streamlit
data/ispv_2025.csv   # preprocessed ISPV snapshot
tests/               # pytest suite + fixtures
scripts/             # CLI entry points
```

## License

MIT — see [LICENSE](LICENSE).
