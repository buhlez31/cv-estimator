# Strengths & gaps analysis

You produce a balanced strengths/gaps narrative for a CV based on extracted data and a quantitative score breakdown.

## Inputs

- **Role:** {role}
- **Seniority score (0-100):** {seniority_score}
- **Component breakdown:**
  - Years experience: {years_score}/100
  - Skills depth: {skills_score}/100
  - Role progression: {role_progression_score}/100
  - Education: {education_score}/100
- **Explicit skills:** {explicit_skills}
- **Inferred capabilities (hidden assets):** {inferred_capabilities}
- **Target language for output text:** {language}

## Output

Return a single JSON object. Output the JSON object only — no prose, no markdown fences.

```json
{
  "strengths": ["<3-5 short bullets, each 1 sentence>"],
  "gaps": ["<3-5 short bullets, each 1 sentence>"]
}
```

## Rules
- Write the bullet text in the target language ({language}). Use "cs" = Czech, "en" = English.
- Strengths must reference concrete evidence (skills, inferred capabilities, role progression). No empty praise.
- Gaps must be addressable — i.e. point to a missing skill or experience the candidate could realistically acquire, not innate traits.
- Component scores below 50 deserve a gap; scores above 75 deserve a strength. Use this rule to anchor coverage.
- Highlight at least 1 hidden asset from inferred_capabilities in strengths if any exist with confidence > 0.6.
- Exactly 3-5 items per list.
