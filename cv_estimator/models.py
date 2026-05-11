"""Pydantic schemas — single source of truth for pipeline output contract."""

from typing import Literal

from pydantic import BaseModel, Field


class SkillEvidence(BaseModel):
    skill: str
    evidence_quote: str
    confidence: float = Field(ge=0.0, le=1.0)
    # Skepticism note — short hedge if the inference might overstate the
    # candidate's role (e.g. "mohl být v týmu, ne sole owner"). Set to None
    # when the evidence is unambiguous.
    caveat: str | None = None


class ScoreBreakdown(BaseModel):
    years_experience: float = Field(ge=0.0, le=100.0)
    skills_depth: float = Field(ge=0.0, le=100.0)
    role_progression: float = Field(ge=0.0, le=100.0)
    education: float = Field(ge=0.0, le=100.0)


class SalaryEstimate(BaseModel):
    # Candidate-specific point estimate
    low: int
    median: int
    high: int
    currency: str = "CZK"
    percentile_position: int = Field(ge=0, le=100)
    # Full ISPV market band for the role — used by the UI range chart so
    # readers see where the candidate sits within the market.
    market_p25: int
    market_p50: int
    market_p75: int
    market_p90: int


class Recommendation(BaseModel):
    action: str
    time_investment: str
    expected_impact: str
    target_skill: str


class TrackResult(BaseModel):
    """One scoring pass — either the skeptical buzzword-only baseline, or
    the hidden-assets-included ceiling."""

    seniority_score: int = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    salary_estimate: SalaryEstimate


class CVAnalysis(BaseModel):
    detected_role: str
    cz_isco_code: str
    role_confidence: float = Field(ge=0.0, le=1.0)
    language: Literal["cs", "en"]

    explicit_skills: list[str]
    inferred_capabilities: list[SkillEvidence]

    # Two parallel analyses. Reader synthesises by eye.
    track_explicit: TrackResult
    track_with_inferred: TrackResult

    strengths: list[str]
    gaps: list[str]
    recommendations: list[Recommendation] = Field(min_length=3, max_length=3)

    processing_metadata: dict
