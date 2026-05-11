# Map job title → CZ-ISCO code (fallback)

You map a job title to its single best-matching 4-digit CZ-ISCO
(Czech occupational classification, ISCO-08 compatible) code.

This is the fallback path — the deterministic keyword-rule mapper
did not find a confident match for the input. Use your knowledge of
ISCO-08 / CZ-ISCO standard occupational nomenclature to pick the most
appropriate code.

## Input

Job title: **{role}**

## CZ-ISCO family reference (ISCO-08 compatible)

Use this 1-digit / 2-digit family map to navigate the code list below:

- **11xx** Chief executives, senior officials, legislators
- **12xx** Administrative / commercial managers (finance, HR, sales/marketing, R&D, business services NEC = 1219)
- **13xx** Production / specialized services managers (incl. ICT services manager = 1330)
- **14xx** Hospitality / retail managers
- **21xx** Science / engineering professionals (physicists 2111, mathematicians 2120, designers 2166)
- **22xx** Health professionals (medical doctors 2211, nurses 2221, pharmacists 2262)
- **23xx** Teaching professionals
- **24xx** Business / administration professionals (accountants 2411, financial analysts 2412/2413, HR 2423, marketing 2431, sales 2433, mgmt analysts 2421/2422)
- **25xx** ICT professionals (systems/business analysts 2511, software developers 2512, web 2513, app programmers 2514, software NEC 2519, DBA 2521, sysadmins 2522, network 2523)
- **26xx** Legal / social / cultural professionals (lawyers 2611)
- **31xx-35xx** Technicians and associate professionals (legal asst 3411, IT user support 3512)
- **41xx-44xx** Clerical support workers (customer service 4222)
- **51xx-54xx** Service / sales workers
- **61xx-63xx** Skilled agricultural / forestry / fishery
- **71xx-75xx** Craft / related trades
- **81xx-83xx** Plant / machine operators, assemblers
- **91xx-96xx** Elementary occupations

### Czech ↔ English translation cheat sheet

| Czech | English | Code family |
|---|---|---|
| Analytik | Analyst | 2422 / 2511 / 2412 (by domain) |
| Vývojář | Developer | 25xx |
| Manažer | Manager | 12xx-14xx (pick by domain) |
| Specialista | Specialist | 24xx-26xx (pick by domain) |
| Konzultant | Consultant | 2421 / 2422 |
| Ředitel | Director | 11xx-14xx (executive level) |
| Inženýr | Engineer | 21xx / 25xx |

### Picking heuristic

1. Translate the title to English first.
2. Pick the most specific family from the breakdown above.
3. Within the family, prefer the dedicated subtype if evident; otherwise
   fall back to the family's "NEC" (not elsewhere classified) code.
4. If the title has no domain hint at all and family is unclear, return
   `"UNMATCHED"`.

## Available codes

Pick exactly one code from this list (codes from the MPSV ISPV 2025
dataset). If none reasonably fits the job title, return `"UNMATCHED"`.

{codes}

## Rules

- Return ONLY a single 4-digit CZ-ISCO code as a string, or `"UNMATCHED"`.
- Prefer the most specific code that fits.
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
