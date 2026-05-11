"""LLM Pass 1 — extract explicit CV facts (role, years, skills, education)."""

from typing import Literal

from pydantic import BaseModel, Field

from cv_estimator import llm


class ExplicitData(BaseModel):
    role: str
    role_seniority_signal: Literal["junior", "mid", "senior", "principal", "unknown"]
    years_experience: int = Field(ge=0, le=60)
    explicit_skills: list[str]
    highest_education: Literal["none", "high_school", "bachelor", "master", "phd"]
    institution: str
    language: Literal["cs", "en"]


def extract(cv_text: str, language: str | None = None) -> ExplicitData:
    """Call LLM #1 and validate the response. `language` arg is informational only."""
    prompt = llm.render_prompt("extract_explicit", cv_text=cv_text)
    payload = llm.call_json(prompt)
    return ExplicitData.model_validate(payload)
