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
    # Candidate-specific point estimate (base monthly gross — ISPV "MZDA")
    low: int
    median: int
    high: int
    currency: str = "CZK"
    percentile_position: int = Field(ge=0, le=100)

    # Full ISPV market band for the role — used by the UI range chart so
    # readers see where the candidate sits within the market.
    market_p10: int = 0
    market_p25: int
    market_p50: int
    market_p75: int
    market_p90: int
    market_mean: int = 0  # ISPV mzdaPrumer; usually > median due to upper-tail outliers

    # ISPV total-comp signal: bonuses + supplements as a share of base. Total
    # comp ≈ base × (1 + bonus_pct + supplement_pct).
    bonus_pct: float = 0.0
    supplement_pct: float = 0.0
    total_comp_low: int = 0
    total_comp_median: int = 0
    total_comp_high: int = 0

    # Statistical reliability of the ISPV row. sample_size is in thousands of
    # employees (ISPV's "pocetZamestnancuMzda"); confidence widens the output
    # band for thin rows.
    sample_size: float = 0.0
    confidence: Literal["low", "medium", "high"] = "high"

    # Region applied (CZ010..CZ080) or None for national. Surface so UI / CLI
    # can attribute the adjustment.
    region: str | None = None
    region_multiplier: float = 1.0


class Recommendation(BaseModel):
    action: str
    time_investment: str
    expected_impact: str
    target_skill: str


class CoverageAttribution(BaseModel):
    """Per-track explanation of which inputs moved the skills coverage
    score. Populated only for non-tech roles where the coverage score
    comes from an LLM call that can list contributing / problematic
    capabilities. Tech roles get None (attribution is implicit from the
    deterministic category-match check)."""

    value_adding: list[str]
    concerns: list[str]


class TrackResult(BaseModel):
    """One scoring view — either the buzzword-only baseline (objective,
    derived from literal CV content) or the hidden-assets-included
    ceiling (adds the inferred-capabilities pass on top)."""

    seniority_score: int = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    salary_estimate: SalaryEstimate
    coverage_attribution: CoverageAttribution | None = None


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
