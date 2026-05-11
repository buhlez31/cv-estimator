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
  "field_of_study": "<the major / specialization / programme name as written in the CV, or empty string>",
  "language": "<one of: cs, en>"
}
```

## Rules
- `language` = primary language of the CV text (cs for Czech, en for English).
- `years_experience` = sum of full-time professional experience; round down. If a date range is given (e.g. "2018 – present"), compute from current year 2025 unless CV implies otherwise.
- `explicit_skills` = only skills literally named in the CV (technologies, tools, languages, frameworks, methodologies). Lower-case. Deduplicate.
- `role_seniority_signal` = derived from the current title keyword (junior, senior, principal, lead, head, manager, etc.) — not from years.
- `role` MUST be:
  1. **Normalized to standard English**: translate Czech titles (e.g. "Analytik" → "Analyst", "Vývojář" → "Developer", "Manažer" → "Manager", "Specialista" → "Specialist", "Ředitel" → "Director").
  2. **Specific, not generic**: never return bare "Analyst" / "Manager" / "Developer" / "Specialist" if domain can be inferred from the CV's work content. Pick the most specific subtype:
     - "Analytik" + data/SQL/dashboards in CV → **"Data Analyst"**
     - "Analytik" + financial reports/accounting → **"Financial Analyst"**
     - "Analytik" + business/strategy/operations → **"Business Analyst"**
     - "Manažer" + IT/engineering → **"Engineering Manager"** or **"ICT Manager"**
     - "Manažer" + marketing/sales → **"Marketing Manager"** / **"Sales Manager"**
     - "Vývojář" + frontend/web → **"Frontend Developer"** or **"Web Developer"**
     - "Vývojář" + backend → **"Backend Developer"** or **"Software Engineer"**
  3. **Include seniority prefix** when the CV title carries one ("Senior", "Lead", etc.).
- `field_of_study` = exact field / major / specialization for the **highest** education entry. Examples: "Computer Science", "Mathematics", "History of Art", "Geoinformatics", "Master of Law", "Marketing". Keep the original-language phrasing if the CV is in Czech (e.g. "Geoinformatika", "Právo"). Empty string if the CV mentions only an institution but no field.
- If a field is unknown, use empty string or 0, never null.

## CV TEXT

{cv_text}
