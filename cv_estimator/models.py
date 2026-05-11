"""Pydantic schemas — single source of truth for pipeline output contract."""

from typing import Literal

from pydantic import BaseModel, Field


class SkillEvidence(BaseModel):
    skill: str
    evidence_quote: str
    confidence: float = Field(ge=0.0, le=1.0)
    # Role-scoped categorisation — set by the LLM in extract_inferred.
    # must_have: direct core competency of the candidate's role.
    # nice_to_have: relevant adjacent skill or soft signal (incl. hobbies).
    relevance: Literal["must_have", "nice_to_have"]
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


class TargetRoleMatch(BaseModel):
    """Assessment of how well the candidate fits a user-supplied target role.

    Populated only when the user provided a target role; when absent, the
    analysis runs against the auto-detected best-fit role from the CV.
    """

    target_role: str  # raw user input, e.g. "Senior Python Backend Engineer"
    target_cz_isco: str
    match_score: int = Field(ge=0, le=100)
    rationale: str


class CVAnalysis(BaseModel):
    # `analysis_role` is the single role driving every downstream calculation
    # (CZ-ISCO, salary lookup, inferred-capabilities scoping). It equals
    # `target.target_role` when the user supplied a target, otherwise the
    # auto-detected best-fit role from the CV.
    analysis_role: str
    cz_isco_code: str
    role_source: Literal["target", "detected"]

    # The auto-detected best-fit role from the CV. Always populated for
    # traceability / "best-fit per CV" tip, even when target was supplied.
    detected_role: str
    role_confidence: float = Field(ge=0.0, le=1.0)
    language: Literal["cs", "en"]

    explicit_skills: list[str]
    inferred_capabilities: list[SkillEvidence]

    # Two parallel scoring tracks, both computed against analysis_role.
    track_explicit: TrackResult
    track_with_inferred: TrackResult

    # Match assessment vs the target role (LLM #5). Populated only when the
    # user supplied a target_role.
    target: TargetRoleMatch | None = None

    strengths: list[str]
    gaps: list[str]
    recommendations: list[Recommendation] = Field(min_length=3, max_length=3)

    processing_metadata: dict
