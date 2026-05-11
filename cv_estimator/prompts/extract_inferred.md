# Extract inferred capabilities (hidden assets)

You analyze CV text to surface skills and capabilities that are **implied by project descriptions and responsibilities but NOT explicitly named** as skills.

This is the product's key differentiator: candidates who describe outcomes ("automated weekly reporting for 200 stakeholders") instead of listing buzzwords should not lose signal.

## Output

Return a single JSON object. Output the JSON object only — no prose, no markdown fences.

```json
{
  "inferred_capabilities": [
    {
      "skill": "<short canonical name, lower-case, e.g. 'stakeholder management', 'sql', 'project management'>",
      "evidence_quote": "<exact quote from CV that justifies this inference, max 200 chars>",
      "confidence": <float 0.0 - 1.0>
    }
  ]
}
```

## Rules
- Only emit a capability if the evidence is concrete (a project, a responsibility, a quantified outcome). No guessing from job titles alone.
- `evidence_quote` must be a verbatim substring of the input CV. Truncate to ≤200 chars.
- `confidence` reflects strength of evidence: 0.9+ for explicit accomplishment with metrics, 0.6-0.8 for clear responsibility, 0.3-0.5 for weak signal.
- Skip skills already buzzword-listed in the CV — focus on the *hidden* ones.
- 3-15 capabilities is the expected range. Quality over quantity.

## Examples of valid inferences

- *"automated weekly reporting for 200 stakeholders"* → `python`/`sql` (automation), `stakeholder management`, `data engineering`
- *"led migration of legacy system to cloud, reduced costs by 30%"* → `cloud architecture`, `cost optimization`, `technical leadership`, `change management`
- *"mentored 4 junior engineers"* → `mentoring`, `leadership scope`

## CV TEXT

{cv_text}
