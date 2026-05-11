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
) -> list[Recommendation]:
    prompt = llm.render_prompt(
        "roadmap",
        role=explicit.role,
        cz_isco=cz_isco,
        seniority_score=seniority_score,
        gaps=json.dumps(gaps, ensure_ascii=False),
        explicit_skills=json.dumps(explicit.explicit_skills, ensure_ascii=False),
        language=explicit.language,
    )
    payload = llm.call_json(prompt)
    return RoadmapData.model_validate(payload).recommendations
