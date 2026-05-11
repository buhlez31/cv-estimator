# Salary growth roadmap

Generate exactly 3 concrete, gap-driven recommendations that, together, would plausibly raise the candidate's market salary by ~30 %.

## Inputs

- **Role:** {role}
- **CZ-ISCO code:** {cz_isco}
- **Current seniority score:** {seniority_score}/100
- **Identified gaps:** {gaps}
- **Existing explicit skills:** {explicit_skills}
- **Target output language:** {language}

## Output

Return a single JSON object. Output the JSON object only — no prose, no markdown fences.

```json
{{
  "recommendations": [
    {{
      "action": "<concrete, verb-first step the candidate can take; 1 sentence>",
      "time_investment": "<e.g. '3-6 months', '6-12 months'>",
      "expected_impact": "<which scoring component improves and how this maps to salary; 1 sentence>",
      "target_skill": "<canonical skill name being acquired or deepened>"
    }}
  ]
}}
```

## Rules
- Exactly 3 recommendations. Not 2, not 4.
- Each `action` must be specific (cite a technology, a certification, a project type — not "learn more"). Verb-first.
- Recommendations should address the lowest-scoring components first (gaps).
- Mix horizons: at least one short-term (≤6 months) and one medium-term (6-18 months) item.
- Write `action` and `expected_impact` in the target language ({language}); keep `target_skill` in English (canonical).
- Avoid duplicates with existing explicit_skills — recommend NEW skills only.
