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
python scripts/run_analysis.py path/to/cv.pdf --target-role "Senior Python Backend Engineer"
```

### Target-role mode

If the candidate is applying to a specific role, supplying it via the
text field in the UI (or `--target-role` on the CLI) anchors the **entire
analysis** on that role: CZ-ISCO lookup, salary band, hidden-asset
scoping, and a 5th LLM call that scores how well the CV matches. When
the field is empty, the auto-detected best-fit role from the CV drives
everything. To compare both views, run the analysis twice — once with
the target field set, once empty.

## Pipeline

```
        ┌──────────────────────────────────────────────────────────┐
        │  pipeline.analyze_cv(file_bytes, target_role=None)       │
        └──────────────────────────────────────────────────────────┘
                              │
                              ▼
 document.extract_text → raw_text → detect_language (cs / en)
                              │
        ├── LLM #1  extractors/explicit.py    → role, years, skills, education,
        │                                       field_of_study (normalized EN)
        │
        ├── analysis_role  =  target_role  if user supplied
        │                  else explicit.role
        │
        ├── LLM #2  extractors/inferred.py    → hidden capabilities scoped to
        │                                       analysis_role (skepticism prompt,
        │                                       caveat field, must/nice relevance)
        │
        ├── salary/role_mapping.py            → CZ-ISCO 4-digit code
        │   keyword rules → LLM fallback (296 codes) → UnmappedRoleError
        │
        ├── scoring/components.py             → ScoreBreakdown (4 axes, 0-100)
        │   ▶ years_experience: years / 15 × 100
        │   ▶ skills_depth (both tracks): LLM-driven coverage scoring
        │       (`skills_coverage` prompt — single mechanism, all role
        │        families; skepticism / overclaim handling lives in the
        │        prompt, not Python). Confident inferred caps (≥0.6) feed
        │        the model as supporting evidence on track B.
        │   ▶ role_progression: title keywords + years
        │   ▶ education: degree base + prestige + role-aware field modifier
        │
        ├── scoring/seniority.py              → weighted (30/35/20/15) → 0-100
        ├── salary/lookup.py                  → SalaryEstimate per track
        │                                       (bucketed: junior/mid/senior/principal)
        │
        ├── coverage_attribution_for(...)     → CoverageAttribution
        │                                       (always populated — surfaces LLM's
        │                                        value_adding + concerns lists)
        │
        ├── LLM #3  explanation/narrative.py  → strengths + gaps for analysis_role
        ├── LLM #4  explanation/roadmap.py    → 3 recommendations for analysis_role
        │
        ├── LLM #5  explanation/match_assess  → target-role fit score + rationale
        │           (only when target_role supplied)
        │
        └── validation/sanity.py              → output-range invariants
                              │
                              ▼
                       CVAnalysis (Pydantic)
```

**LLM call count per analysis (Phase 11 — single all-LLM coverage):**
- No target role → **4 + 2** = 6 calls (4 pipeline + 2 coverage tracks) (~$0.045)
- With target role → **5 + 2** = 7 calls (~$0.055)
- Plus 1 conditional LLM fallback for `role_mapping` on unknown titles (~$0.003)

Four LLM calls, each driven by a prompt loaded from
`cv_estimator/prompts/*.md` (kept as artifacts, not Python strings).
The output schema in [`cv_estimator/models.py`](cv_estimator/models.py) is the
contract that every module builds around — *output-first design*.

## Data approach

**Salary source: MPSV ISPV open data** — [data.mpsv.cz/web/data/ispv-zamestnani](https://data.mpsv.cz/web/data/ispv-zamestnani).

Official Czech earnings statistics, published by the Ministry of Labour and
Social Affairs with quantiles (P25 / P50 / P75 / P90) per CZ-ISCO occupation
code. Used by ČSÚ for pension valorization — defensible, free, no scraping.

The committed [`data/ispv_2025.csv`](data/ispv_2025.csv) is a 14-row snapshot
generated from the official MPSV JSON export (period: `rok 2025`, sphere:
`MZDOVA` — private-sector wages, where almost all IT employment sits).
Filtered to IT-relevant CZ-ISCO codes (251x developers, 252x DB / network,
1330 ICT managers, 351x technicians). The preprocessing pipeline is in
[`scripts/prepare_ispv_data.py`](scripts/prepare_ispv_data.py); drop the raw
`ispv-zamestnani.json` into `data/raw/` and the script regenerates the
lookup table.

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

### Education: role-aware field relevance

`_education_score` factors in the candidate's `field_of_study` (extracted
by LLM #1) against the analysis role's family. Heuristic role-family +
field-family classifiers (`ROLE_FAMILY_KEYWORDS`, `FIELD_FAMILY_KEYWORDS`
in [`config.py`](cv_estimator/config.py)) bucket each side into one of
~8 families.

**Lowered base map** so the typical case isn't already saturated before
the relevance modifier applies:

| Degree | Base |
|---|---|
| none | 0 |
| high_school | 10 |
| bachelor | 30 |
| master | 50 |
| phd | 70 |

**+5** prestige bonus on top if the institution is in
`PRESTIGE_INSTITUTION_KEYWORDS`.

**Field-relevance modifier:**

| Relationship | Effect on score |
|---|---|
| Same family (e.g. CS field + Software Engineer role) | **+5** match bonus |
| Adjacent pair (e.g. Geoinformatika + Research Analyst, CS + CTO) | 0 |
| Different families (e.g. History + Backend Engineer) | **-25** hard penalty |
| Field empty (LLM couldn't find one) | base × **0.5** half-credit |
| Either side unclassified | 0 (no signal, no penalty) |
| `highest_education = "none"` | **0** regardless of anything else |

Worked examples (assuming ČVUT, which has the +5 prestige bonus):

- Master CS + Senior Backend Engineer (match) → 50 + 5 + 5 = **60**
- Master Geoinformatika + Research Analyst (adjacent) → 50 + 5 = **55**
- Master History + Senior Backend Engineer (mismatch) → 50 + 5 − 25 = **30**
- PhD History + Senior Backend Engineer (mismatch, no prestige) → 70 − 25 = **45**
- Master CS, no field listed + Backend Engineer (half credit) → (50 + 5) × 0.5 = **27.5**
- No degree listed → **0** regardless of role / institution

## The hidden-assets thesis

The product differentiator is `inferred_capabilities` ([extractors/inferred.py](cv_estimator/extractors/inferred.py)):
a second LLM pass that finds skills *implied* by project descriptions
("automated weekly reporting for 200 stakeholders" → `python`, `sql`,
`stakeholder management`) instead of the buzzword list at the bottom of the
CV.

### Two parallel analysis tracks

The pipeline emits **two independent scoring tracks** so the reader sees
buzzword vs hidden-assets analyses side-by-side instead of a single blended
number:

- **`track_explicit`** — buzzword baseline. The LLM (`skills_coverage`
  prompt) returns `coverage_percent` for the role given only the
  literal CV content. 100 means "every core competency a hiring
  manager would check for this role is demonstrated by the CV's
  listed skills".
- **`track_with_inferred`** — same coverage prompt, but inferred
  capabilities with `confidence ≥ 0.6` are also handed to the model as
  supporting evidence. The model decides how much (if at all) they
  lift the score, capped at ~15 points per its rubric.

The split applies to **every role family** — tech, business, marketing,
legal, healthcare, design, etc. — through a single LLM-driven
mechanism. Skepticism / overclaim handling (caveat-heavy or
low-confidence inferred passes) lives in the prompt itself: see
`cv_estimator/prompts/skills_coverage.md` for the rubric and rules.

Worked examples:
- Backend Engineer CV listing python, postgres, kafka, k8s, terraform
  → LLM returns ~70 %, flags observability + CI/CD as missing core.
- Marketing Manager CV listing google analytics, seo, hubspot, content
  strategy, email automation → LLM returns ~70 %, flags paid
  acquisition + brand strategy as missing core.
- Lawyer CV listing contract drafting, litigation, compliance → LLM
  returns ~60 %, flags GDPR + M&A + court representation as missing core.

Each track ships its own `seniority_score` and `salary_estimate`. The UI
renders them in side-by-side cards and a market-range chart shows both
points within the ISPV P25-P90 band for the role.

When the two tracks coincide (e.g. CV already lists every skill explicitly),
that is itself a signal: there is nothing for the inferred pass to surface.
When they diverge, the gap measures *how much the candidate's description
style under-represents them* — which is the case the standard buzzword
filters fail at.

### Role-scoped + skepticism (inferred-pass only)

Skepticism applies only to the inferred-capabilities pass — the buzzword
baseline is the objective view; the inferred extraction is the part that
gets the conservative treatment.

Looking at real-CV output, the inferred pass had a tendency to over-attribute
(e.g. inferring "community manager" from being the analyst on a community
project) AND to surface capabilities irrelevant to the candidate's actual
role (e.g. "marketing copywriting" for a backend engineer). The
[`extract_inferred.md`](cv_estimator/prompts/extract_inferred.md) prompt
now:

- **Receives the detected role** as a parameter and scopes every inference
  to that role. Capabilities outside the role's domain are dropped.
- **Scans the WHOLE CV**, not just work experience — education, certs,
  languages, hobbies, interests. Soft signals from hobbies (team sports
  → collaboration, marathon → discipline) are valid but get LOW
  confidence (0.3–0.5).
- **Classifies each capability** as either `must_have` (direct core
  competency of the role) or `nice_to_have` (adjacent skill, soft signal).
  Both are fed to the LLM coverage scorer as supporting evidence —
  the coverage prompt decides how much each lifts (or fails to lift)
  the score.
- **Enforces an explicit skepticism protocol** on top:

1. Anchor confidence at 0.5 by default — move to 0.8+ only with concrete
   numeric or role-scoped evidence.
2. Title-only inferences are capped at confidence 0.4.
3. The model emits an optional `caveat` field beside each capability when
   the inference rests on team-scope ambiguity, peak metrics, or
   short-tenure roles ("mohl být v týmu, ne sole owner").
4. Second-order inferential leaps are rejected — "miss a hidden asset"
   beats "fabricate one".

The UI renders each `caveat` in italics under the evidence quote so the
reader sees the model's self-doubt and can discount accordingly.

**A/B buzzword test** ([`scripts/generate_synthetic_cvs.py`](scripts/generate_synthetic_cvs.py))
produces two CVs for the same fictional candidate:

- **Variant A** — buzzword-heavy: bullet list of technologies and methods.
- **Variant B** — outcome-driven: same person, same skills, but described
  as *what they did* and *what they delivered* (with metrics).

Expected: A and B land within roughly the same band on `track_with_inferred`.
If A scores significantly higher even on the inferred track, the inferred
pass is failing and the prompt needs work.

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
data/ispv_2025.csv            # preprocessed ISPV snapshot (rok 2025, MZDOVA)
tests/                        # pytest suite + fixtures
scripts/                      # CLI entry points
```

## License

MIT — see [LICENSE](LICENSE).
