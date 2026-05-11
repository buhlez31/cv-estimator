"""Pydantic schemas — single source of truth for pipeline output contract."""

from typing import Literal

from pydantic import BaseModel, Field


class SkillEvidence(BaseModel):
    skill: str
    evidence_quote: str
    confidence: float = Field(ge=0.0, le=1.0)


class ScoreBreakdown(BaseModel):
    years_experience: float = Field(ge=0.0, le=100.0)
    skills_depth: float = Field(ge=0.0, le=100.0)
    role_progression: float = Field(ge=0.0, le=100.0)
    education: float = Field(ge=0.0, le=100.0)


class SalaryEstimate(BaseModel):
    low: int
    median: int
    high: int
    currency: str = "CZK"
    percentile_position: int = Field(ge=0, le=100)


class Recommendation(BaseModel):
    action: str
    time_investment: str
    expected_impact: str
    target_skill: str


class CVAnalysis(BaseModel):
    detected_role: str
    cz_isco_code: str
    role_confidence: float = Field(ge=0.0, le=1.0)
    language: Literal["cs", "en"]

    seniority_score: int = Field(ge=0, le=100)
    breakdown: ScoreBreakdown

    explicit_skills: list[str]
    inferred_capabilities: list[SkillEvidence]

    salary_estimate: SalaryEstimate

    strengths: list[str]
    gaps: list[str]
    recommendations: list[Recommendation] = Field(min_length=3, max_length=3)

    processing_metadata: dict
