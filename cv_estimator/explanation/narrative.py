"""LLM #3 — strengths & gaps narrative."""

import json

from pydantic import BaseModel

from cv_estimator import llm
from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown


class StrengthsGaps(BaseModel):
    strengths: list[str]
    gaps: list[str]


def analyze(
    explicit: ExplicitData,
    inferred: InferredData,
    breakdown: ScoreBreakdown,
    seniority_score: int,
    analysis_role: str | None = None,
) -> StrengthsGaps:
    """Generate strengths + gaps narrative.

    `analysis_role` is the role to evaluate the candidate against (target
    role if user supplied one, otherwise the detected role). When omitted,
    falls back to `explicit.role` for backward compatibility.
    """
    inferred_brief = [
        {"skill": c.skill, "confidence": round(c.confidence, 2)}
        for c in inferred.inferred_capabilities
    ]
    prompt = llm.render_prompt(
        "strengths_gaps",
        role=analysis_role or explicit.role,
        seniority_score=seniority_score,
        years_score=int(breakdown.years_experience),
        skills_score=int(breakdown.skills_depth),
        role_progression_score=int(breakdown.role_progression),
        education_score=int(breakdown.education),
        explicit_skills=json.dumps(explicit.explicit_skills, ensure_ascii=False),
        inferred_capabilities=json.dumps(inferred_brief, ensure_ascii=False),
        language=explicit.language,
    )
    payload = llm.call_json(prompt)
    return StrengthsGaps.model_validate(payload)
