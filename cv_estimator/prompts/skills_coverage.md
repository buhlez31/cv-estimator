# Skills coverage scoring

You evaluate what percentage (0–100) of the core skills, tools, and
competencies a hiring manager for the given role typically expects are
demonstrated by the candidate's CV data. Works for any role family —
tech, business, marketing, legal, healthcare, design, etc. Use your
knowledge of what each role requires.

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

## Scoring rubric

- **100** — Comprehensive coverage of the role's core competencies. CV
  demonstrates every typical category a hiring manager would check.
- **75** — Covers most cores with one or two gaps.
- **50** — About half the cores covered. Significant gaps in critical
  competencies.
- **25** — Few cores covered. CV looks weakly aligned to the role.
- **0** — No relevant skills / competencies demonstrated.

## Rules

1. **Be conservative.** Generic skills like "communication", "teamwork",
   "Microsoft Office" do NOT count toward coverage of a senior role.
   Require domain-specific competencies.
2. **Skepticism on overclaim signals.** If the inferred capabilities
   show high caveat density (most caps carry caveats) or low average
   confidence (typical confidence below ~0.4), lower the score by
   10–15 points below what the listed inputs would otherwise warrant —
   they may be overselling. Capture these capabilities in `concerns`.
3. **Attribution.** `value_adding_capabilities` = names from the input
   lists that genuinely advanced the candidate's fit. `concerns` =
   names that didn't help, were caveat-heavy, or weren't actually
   role-relevant. Pick names from the lists provided — don't invent.
   Empty lists are OK if nothing notable contributed / concerned.
4. **`missing_core`**: 0–5 critical competencies a hiring manager
   would expect but the candidate's data doesn't demonstrate. Short,
   specific strings (e.g. "Kubernetes", "FP&A modelling", "Contract
   law", "Patient triage").
5. **Inferred capabilities are hints, not proof.** They count as
   supporting evidence but should not move the score by more than
   ~15 points compared to explicit-only scoring.
6. **Czech / European market anchor.** For ambiguous role titles,
   anchor on what the title commonly requires in the Czech / European
   market.
7. **Don't invent skills.** Score what's demonstrated, not what could be.

## ISCO-08 family reference (optional context)

If you need to ground your understanding of a role's typical
competencies, recall:

- **11xx–14xx** Managers (chief executives, finance, HR, marketing,
  R&D, hospitality)
- **21xx** Science / engineering professionals (incl. designers,
  architects)
- **22xx** Health professionals (doctors, nurses, pharmacists)
- **23xx** Teaching professionals
- **24xx** Business / administration professionals (finance, HR,
  marketing, sales)
- **25xx** ICT professionals (developers, DBAs, network specialists)
- **26xx** Legal / social / cultural professionals
- **31xx–35xx** Technicians and associate professionals

## Examples

- Role "Senior Backend Engineer", explicit `["python", "postgres",
  "kubernetes", "kafka", "aws"]`, no inferred →
  `{"coverage_percent": 70, "missing_core": ["observability tooling",
  "CI/CD"], "value_adding_capabilities": ["kubernetes", "kafka"],
  "concerns": []}`

- Role "Marketing Manager", explicit `["google analytics", "seo",
  "hubspot", "content strategy", "email automation"]`, no inferred →
  `{"coverage_percent": 70, "missing_core": ["paid acquisition",
  "brand strategy"], "value_adding_capabilities": ["google analytics",
  "seo"], "concerns": []}`

- Role "Lawyer", explicit `["contract drafting", "litigation",
  "compliance"]`, no inferred → `{"coverage_percent": 60,
  "missing_core": ["GDPR", "M&A", "Court representation"],
  "value_adding_capabilities": ["litigation"], "concerns": []}`

- Role "Marketing Manager", explicit `["python", "sql"]`, no
  inferred → `{"coverage_percent": 5, "missing_core": ["marketing
  strategy", "content", "seo", "paid ads", "analytics"],
  "value_adding_capabilities": [], "concerns": ["python", "sql"]}`
