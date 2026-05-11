"""LLM #5 — target-role fit assessment.

Compares the candidate's extracted profile (role, years, explicit skills,
inferred capabilities) against a target role string supplied by the user
and returns a fit score plus a short rationale in the CV's language.
"""

import json

from pydantic import BaseModel, Field

from cv_estimator import llm
from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.extractors.inferred import InferredData


class MatchResult(BaseModel):
    match_score: int = Field(ge=0, le=100)
    rationale: str


def evaluate(
    target_role: str,
    explicit: ExplicitData,
    inferred: InferredData,
) -> MatchResult:
    inferred_brief = [
        {"skill": c.skill, "confidence": round(c.confidence, 2)}
        for c in inferred.inferred_capabilities
    ]
    prompt = llm.render_prompt(
        "match_assess",
        target_role=target_role,
        candidate_role=explicit.role,
        years_experience=explicit.years_experience,
        explicit_skills=json.dumps(explicit.explicit_skills, ensure_ascii=False),
        inferred_capabilities=json.dumps(inferred_brief, ensure_ascii=False),
        language=explicit.language,
    )
    payload = llm.call_json(prompt)
    return MatchResult.model_validate(payload)
