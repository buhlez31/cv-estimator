"""LLM Pass 2 — extract inferred capabilities (hidden assets).

This is the product differentiator: skills implied by project descriptions
but not buzzword-listed.
"""

from pydantic import BaseModel

from cv_estimator import llm
from cv_estimator.models import SkillEvidence


class InferredData(BaseModel):
    inferred_capabilities: list[SkillEvidence]


def extract(cv_text: str, language: str | None = None) -> InferredData:
    prompt = llm.render_prompt("extract_inferred", cv_text=cv_text)
    payload = llm.call_json(prompt)
    return InferredData.model_validate(payload)
