# Extract explicit CV facts

You are a CV parser. Read the CV text below and extract ONLY information that is explicitly stated. Do NOT infer or guess.

Return a single JSON object matching this schema. Output the JSON object only — no prose, no markdown fences.

```json
{
  "role": "<current or most recent job title, normalized to English, e.g. 'Data Scientist'>",
  "role_seniority_signal": "<one of: junior, mid, senior, principal, unknown>",
  "years_experience": <integer total years of professional work, sum across roles if listed>,
  "explicit_skills": ["<skill 1>", "<skill 2>", "..."],
  "highest_education": "<one of: none, high_school, bachelor, master, phd>",
  "institution": "<name of highest-ed institution or empty string>",
  "language": "<one of: cs, en>"
}
```

## Rules
- `language` = primary language of the CV text (cs for Czech, en for English).
- `years_experience` = sum of full-time professional experience; round down. If a date range is given (e.g. "2018 – present"), compute from current year 2025 unless CV implies otherwise.
- `explicit_skills` = only skills literally named in the CV (technologies, tools, languages, frameworks, methodologies). Lower-case. Deduplicate.
- `role_seniority_signal` = derived from the current title keyword (junior, senior, principal, lead, head, manager, etc.) — not from years.
- If a field is unknown, use empty string or 0, never null.

## CV TEXT

{cv_text}
