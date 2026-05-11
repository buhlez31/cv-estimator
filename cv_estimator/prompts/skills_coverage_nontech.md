# Skills coverage scoring for non-tech role

You evaluate what percentage (0-100) of the core skills, tools, and
competencies a hiring manager for the given role typically expects are
demonstrated by the candidate's CV data.

This is the **non-tech path** — the deterministic tech-stack category
checker doesn't fit roles like marketing, sales, legal, healthcare,
business management, etc. Use your knowledge of what each role family
requires.

## Inputs

- **Target role:** {role}
- **Explicit skills from CV:** {explicit_skills}
- **Inferred capabilities** (confident-only, optional): {inferred_capabilities}

## Output

Single JSON object. No prose, no markdown fences.

```json
{
  "coverage_percent": <int 0-100>,
  "missing_core": ["<short skill name>", "..."],
  "value_adding_capabilities": ["<skill name from inputs that lifted the score>"],
  "concerns": ["<skill name from inputs that pulled the score down or didn't help>"]
}
```

### Attribution fields

- `value_adding_capabilities`: names of **inferred capabilities or
  explicit skills from the inputs** that genuinely advanced the
  candidate's fit for `{role}`. Pick names from the lists provided —
  don't invent. Empty list if nothing materially contributed.
- `concerns`: names of inputs that *should have helped* but had caveats,
  low confidence, or weren't actually role-relevant. Empty list if no
  notable concerns. Use this to flag overclaim signals.

## Scoring rubric

- **100** — Comprehensive coverage of the role's core competencies. CV
  demonstrates every typical category a hiring manager would check.
- **75** — Covers most cores with one or two gaps.
- **50** — About half the cores covered. Significant gaps in critical
  competencies.
- **25** — Few cores covered. CV looks weakly aligned to the role.
- **0** — No relevant skills / competencies demonstrated.

## Rules

1. Be conservative. Generic skills like "communication", "teamwork",
   "Microsoft Office" do NOT count toward coverage of a senior role.
   Require domain-specific competencies.
2. `missing_core` = 0-5 critical competencies a hiring manager would
   expect but the candidate's data doesn't demonstrate. Short, specific
   strings (e.g. "Google Analytics", "FP&A modelling", "Contract law",
   "Patient triage"). Empty list if coverage is comprehensive.
3. Inferred capabilities (when provided) count as supporting evidence
   but should not move the score by more than ~15 points compared to
   explicit-only scoring — they're hints, not proof.
4. For ambiguous roles, anchor on what the JOB TITLE most commonly
   requires in the Czech / European market.
5. Do NOT invent skills. Score what's demonstrated, not what could be.

## Examples

- Role "Marketing Manager", explicit skills `["google analytics", "seo",
  "hubspot", "content strategy", "email automation"]`, no inferred →
  `{"coverage_percent": 70, "missing_core": ["paid acquisition", "brand strategy"]}`
- Role "Lawyer", explicit skills `["contract drafting", "litigation",
  "compliance"]`, no inferred → `{"coverage_percent": 60, "missing_core":
  ["GDPR", "M&A", "Court representation"]}`
- Role "Marketing Manager", explicit skills `["python", "sql"]`, no
  inferred → `{"coverage_percent": 5, "missing_core": ["marketing
  strategy", "content", "seo", "paid ads", "analytics"]}`
