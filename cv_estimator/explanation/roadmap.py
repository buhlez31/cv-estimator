"""LLM #4 — generate exactly 3 gap-driven recommendations."""

import json

from pydantic import BaseModel, Field

from cv_estimator import llm
from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.models import Recommendation


class RoadmapData(BaseModel):
    recommendations: list[Recommendation] = Field(min_length=3, max_length=3)


def generate(
    explicit: ExplicitData,
    gaps: list[str],
    seniority_score: int,
    cz_isco: str,
    analysis_role: str | None = None,
) -> list[Recommendation]:
    """Generate 3 gap-driven recommendations targeted at the analysis role.

    `analysis_role` is the role to grow into (target role when user supplied
    one, otherwise the detected role). Falls back to `explicit.role`.
    """
    prompt = llm.render_prompt(
        "roadmap",
        role=analysis_role or explicit.role,
        cz_isco=cz_isco,
        seniority_score=seniority_score,
        gaps=json.dumps(gaps, ensure_ascii=False),
        explicit_skills=json.dumps(explicit.explicit_skills, ensure_ascii=False),
        language=explicit.language,
    )
    payload = llm.call_json(prompt)
    return RoadmapData.model_validate(payload).recommendations
