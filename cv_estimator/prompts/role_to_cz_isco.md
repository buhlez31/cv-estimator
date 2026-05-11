# Map job title → CZ-ISCO code (fallback)

You map a job title to its single best-matching 4-digit CZ-ISCO
(Czech occupational classification, ISCO-08 compatible) code.

This is the fallback path — the deterministic keyword-rule mapper
did not find a confident match for the input. Use your knowledge of
ISCO-08 / CZ-ISCO standard occupational nomenclature to pick the most
appropriate code.

## Input

Job title: **{role}**

## Available codes

Pick exactly one code from this list (codes from the MPSV ISPV 2025
dataset). If none reasonably fits the job title, return `"UNMATCHED"`.

{codes}

## Rules

- Return ONLY a single 4-digit CZ-ISCO code as a string, or `"UNMATCHED"`.
- Prefer the most specific code that fits. E.g. for "Quantum Computing
  Researcher" prefer a science / research code over a generic developer
  code.
- For ambiguous titles where seniority is the only signal (e.g. "Senior
  Director" without domain context), pick the closest management code.
- Do NOT invent codes outside the provided list.

## Output

Single JSON object, no prose, no markdown fences:

```json
{"code": "XXXX"}
```

or, when nothing fits:

```json
{"code": "UNMATCHED"}
```
