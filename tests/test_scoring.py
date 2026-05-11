"""Unit tests for scoring/components.py and scoring/seniority.py."""

from unittest.mock import patch

import pytest

from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown, SkillEvidence
from cv_estimator.scoring import components, seniority


@pytest.fixture(autouse=True)
def _stub_llm_calls():
    """All skills_coverage scoring routes through the LLM. Stub call_json
    with a stable 50 % default so tests can focus on whichever component
    they're actually asserting. Tests that want a specific LLM response
    override with their own patch.
    """
    components._llm_coverage_raw.cache_clear()

    def _stub(prompt: str) -> dict:
        if "Skills coverage scoring" in prompt:
            return {
                "coverage_percent": 50,
                "missing_core": [],
                "value_adding_capabilities": [],
                "concerns": [],
            }
        # Any other LLM hit during a test means a missing mock — fail loud.
        raise AssertionError(f"Unexpected LLM call in test_scoring: {prompt[:100]}")

    with patch("cv_estimator.llm.call_json", side_effect=_stub):
        yield
    components._llm_coverage_raw.cache_clear()


def test_seniority_is_weighted_average():
    b = ScoreBreakdown(years_experience=100, skills_depth=100, role_progression=100, education=100)
    assert seniority.compute(b) == 100

    b0 = ScoreBreakdown(years_experience=0, skills_depth=0, role_progression=0, education=0)
    assert seniority.compute(b0) == 0


def test_seniority_clamped_to_range():
    b = ScoreBreakdown(years_experience=80, skills_depth=70, role_progression=85, education=60)
    score = seniority.compute(b)
    assert 0 <= score <= 100
    # 80*0.30 + 70*0.35 + 85*0.20 + 60*0.15 = 74
    assert score == 74


def test_skills_coverage_uses_llm_for_any_role(explicit_senior_dev):
    """All roles route through the LLM-based coverage scorer. Autouse stub
    returns 50 % default; verify the helper is called and its output
    reaches `skills_depth`."""
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Software Engineer")
    assert b.skills_depth == 50.0


def test_skills_coverage_inferred_changes_score(explicit_senior_dev, inferred_senior_dev):
    """Baseline (no inferred) vs with-inferred go through the LLM twice.
    Mock returns different scores per call so we can verify inferred
    affects the result."""
    role = "Senior Software Engineer"

    responses = iter(
        [
            {
                "coverage_percent": 60,
                "missing_core": [],
                "value_adding_capabilities": [],
                "concerns": [],
            },
            {
                "coverage_percent": 75,
                "missing_core": [],
                "value_adding_capabilities": ["aws"],
                "concerns": [],
            },
        ]
    )

    def _stub(_prompt: str) -> dict:
        return next(responses)

    components._llm_coverage_raw.cache_clear()
    with patch("cv_estimator.llm.call_json", side_effect=_stub):
        b_explicit = components.compute_explicit_only(explicit_senior_dev, role)
        b_full = components.compute_with_inferred(explicit_senior_dev, inferred_senior_dev, role)
    assert b_explicit.skills_depth == 60.0
    assert b_full.skills_depth == 75.0


def test_components_senior_dev_full(explicit_senior_dev, inferred_senior_dev):
    """senior_dev fixture under all-LLM coverage, analysis_role with
    `senior` keyword:
    - Years: cap 15 (senior keyword) → 8/15*100 ≈ 53
    - Skills coverage: autouse stub returns 50 %
    - Role progression: senior keyword + 8 years (no +5 since <10) = 80
    - Education: master 50 + ČVUT prestige 5 + CS match +5 = 60
    """
    b = components.compute_with_inferred(
        explicit_senior_dev, inferred_senior_dev, "Senior Software Engineer"
    )
    assert 50 <= b.years_experience <= 55
    assert b.skills_depth == 50.0
    assert b.role_progression == 80.0
    assert b.education == 60.0


def test_components_junior_support(explicit_junior_support, inferred_empty):
    """Analysis_role "Junior IT Support" → junior keyword fires:
    - Years: cap 3 (junior) → 1/3*100 ≈ 33
    - Role progression: junior keyword → 25
    - Education: bachelor 30 + VŠE prestige 5 + unknown field family → 35
    """
    b = components.compute_with_inferred(
        explicit_junior_support, inferred_empty, "Junior IT Support"
    )
    assert 30 <= b.years_experience <= 35
    assert b.skills_depth == 50.0
    assert b.role_progression == 25.0
    assert b.education == 35.0


def test_years_and_role_react_to_analysis_role(explicit_senior_dev, inferred_empty):
    """Same CV → different years_experience and role_progression depending
    on the analyzed role. Demonstrates the target-driven reactivity."""
    senior = components.compute_with_inferred(
        explicit_senior_dev, inferred_empty, "Senior Backend Engineer"
    )
    junior = components.compute_with_inferred(
        explicit_senior_dev, inferred_empty, "Junior Backend Engineer"
    )
    principal = components.compute_with_inferred(
        explicit_senior_dev, inferred_empty, "Principal Engineer"
    )
    # 8 years saturates against junior cap (3), maxes mid-tier cap (10),
    # and lands at 8/15 ≈ 53 against senior, 8/20 = 40 against principal.
    assert junior.years_experience == 100.0
    assert 50 <= senior.years_experience <= 55
    assert 39 <= principal.years_experience <= 41
    # Role progression flips with the keyword.
    assert junior.role_progression == 25.0
    assert senior.role_progression == 80.0
    assert principal.role_progression == 95.0


def test_coverage_attribution_universal():
    """`coverage_attribution_for` returns a CoverageAttribution for every
    role family (no tech→None branch)."""
    inferred = InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="seo",
                evidence_quote="ev",
                confidence=0.8,
                relevance="must_have",
            ),
        ]
    )
    with patch(
        "cv_estimator.llm.call_json",
        return_value={
            "coverage_percent": 75,
            "missing_core": [],
            "value_adding_capabilities": ["seo"],
            "concerns": ["hubspot"],
        },
    ):
        components._llm_coverage_raw.cache_clear()
        attr = components.coverage_attribution_for(
            "Marketing Manager",
            ["seo", "hubspot"],
            inferred.inferred_capabilities,
            include_inferred=True,
        )
    assert attr is not None
    assert attr.value_adding == ["seo"]
    assert attr.concerns == ["hubspot"]

    # Tech role also returns attribution now.
    with patch(
        "cv_estimator.llm.call_json",
        return_value={
            "coverage_percent": 80,
            "missing_core": [],
            "value_adding_capabilities": ["python"],
            "concerns": [],
        },
    ):
        components._llm_coverage_raw.cache_clear()
        attr_tech = components.coverage_attribution_for(
            "Senior Backend Engineer", ["python"], [], include_inferred=False
        )
    assert attr_tech is not None
    assert attr_tech.value_adding == ["python"]


# ----- Education field-relevance modifier ------------------------------------


def test_education_tech_field_tech_role_gets_bonus(explicit_senior_dev):
    """CS degree + Backend Engineer (tech role) → +5 match bonus."""
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    # master 50 + ČVUT prestige 5 + match bonus 5 = 60
    assert b.education == 60.0


def test_education_non_tech_field_tech_role_gets_hard_penalty(explicit_senior_dev):
    """History degree + Backend Engineer (tech) → -25 hard penalty."""
    explicit_senior_dev.field_of_study = "History"
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    # master 50 + ČVUT prestige 5 - 25 = 30
    assert b.education == 30.0


def test_education_adjacent_field_tech_role_neutral(explicit_senior_dev):
    """Geoinformatika (tech_adjacent) + Research Analyst (tech) → 0 modifier."""
    explicit_senior_dev.field_of_study = "Geoinformatika"
    b = components.compute_explicit_only(explicit_senior_dev, "Research Analyst")
    # master 50 + ČVUT prestige 5 + 0 = 55
    assert b.education == 55.0


def test_education_empty_field_half_credit(explicit_senior_dev):
    """Empty field_of_study → half credit on base + prestige."""
    explicit_senior_dev.field_of_study = ""
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    # (master 50 + ČVUT prestige 5) × 0.5 = 27.5
    assert b.education == 27.5


def test_education_marketing_role_with_cs_field_adjacent(explicit_senior_dev):
    """CS + Marketing Manager — 'manager' wins business_mgmt first; pair
    (business_mgmt, tech) is in ROLE_FIELD_ADJACENT_PAIRS → 0 modifier."""
    b = components.compute_explicit_only(explicit_senior_dev, "Marketing Manager")
    # master 50 + ČVUT prestige 5 + 0 = 55
    assert b.education == 55.0


def test_education_cto_with_cs_field_adjacent(explicit_senior_dev):
    """CTO (business_mgmt) + CS (tech) → adjacent → 0 modifier."""
    b = components.compute_explicit_only(explicit_senior_dev, "CTO")
    # master 50 + ČVUT prestige 5 + 0 = 55
    assert b.education == 55.0


def test_education_none_returns_zero(explicit_senior_dev):
    """No degree → 0 regardless of prestige, field, or role match.
    User direction: 'kdo nema education uvedeny tak 0 za education navic'."""
    explicit_senior_dev.highest_education = "none"
    explicit_senior_dev.field_of_study = "Computer Science"
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    assert b.education == 0.0


def test_education_phd_humanities_for_tech_role_dropped(explicit_senior_dev):
    """PhD History + Backend Engineer → 70 + 0 prestige - 25 penalty = 45.
    Even at PhD level, irrelevant field carries a real cost."""
    explicit_senior_dev.highest_education = "phd"
    explicit_senior_dev.institution = "Random University"  # not in prestige list
    explicit_senior_dev.field_of_study = "History"
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    assert b.education == 45.0


def test_classify_role_family_directly():
    assert components._classify_role_family("Senior Backend Engineer") == "tech"
    assert components._classify_role_family("CTO") == "business_mgmt"
    assert components._classify_role_family("UX Designer") == "design_creative"
    assert components._classify_role_family("Sales Account Manager") in {
        "business_mgmt",
        "sales_biz_dev",
    }  # "manager" matches business_mgmt first per dict order
    assert components._classify_role_family("Some Weird Title") == "unknown"


def test_classify_field_family_directly():
    assert components._classify_field_family("Computer Science") == "tech"
    assert components._classify_field_family("Geoinformatika") == "tech_adjacent"
    assert components._classify_field_family("History of Art") == "humanities"
    assert components._classify_field_family("Master of Law") == "legal"
    assert components._classify_field_family("") == "unknown"
    assert components._classify_field_family("Random Field") == "unknown"
