"""Unit tests for scoring/components.py and scoring/seniority.py."""

from unittest.mock import patch

import pytest

from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown, SkillEvidence
from cv_estimator.scoring import components, seniority


@pytest.fixture(autouse=True)
def _stub_llm_calls():
    """Most test_scoring cases exercise the deterministic tech-coverage
    path. A few hit non-tech roles which now go through the LLM-based
    coverage scorer — stub call_json with a stable 50 % default so the
    test can focus on whichever component it's actually asserting.
    Tests that want a specific LLM response override with their own patch.
    """
    components._llm_coverage_nontech_raw.cache_clear()

    def _stub(prompt: str) -> dict:
        if "Skills coverage scoring for non-tech role" in prompt:
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
    components._llm_coverage_nontech_raw.cache_clear()


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


def test_skills_coverage_tech_baseline(explicit_senior_dev):
    """senior_dev explicit_skills cover 4 of 9 tech categories:
    language (python), container_orchestration (k8s + terraform),
    database (postgres), messaging_streaming (kafka). → 44.4%."""
    b_explicit = components.compute_explicit_only(explicit_senior_dev, "Senior Software Engineer")
    assert abs(b_explicit.skills_depth - 44.4) < 0.2


def test_skills_coverage_inferred_unlocks_new_category(explicit_senior_dev, inferred_senior_dev):
    """inferred_senior_dev fixture includes 'aws' capability (confidence
    0.8, above threshold) — unlocks cloud_platform category. Now 9 total
    categories (added ml_data_science). Baseline 4/9 ≈ 44.4 %,
    with-inferred 5/9 ≈ 55.6 %. Caveat ratio 1/3 < 0.5 and avg
    confidence (0.85+0.8+0.75)/3 = 0.8 ≥ 0.4 → no overclaim penalty."""
    role = "Senior Software Engineer"
    b_explicit = components.compute_explicit_only(explicit_senior_dev, role)
    b_full = components.compute_with_inferred(explicit_senior_dev, inferred_senior_dev, role)
    assert abs(b_explicit.skills_depth - 44.4) < 0.2
    assert abs(b_full.skills_depth - 55.6) < 0.2


def test_skills_coverage_low_confidence_inferred_does_not_unlock(explicit_senior_dev):
    """Inferred capability below confidence threshold (0.6) does NOT count
    toward coverage. Plus low avg confidence (0.4) triggers overclaim
    penalty → with-inferred drops below baseline."""
    weak_inferred = InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="aws",
                evidence_quote="mentioned cloud experience",
                confidence=0.4,  # below threshold + triggers overclaim
                relevance="nice_to_have",
            ),
        ]
    )
    b = components.compute_with_inferred(
        explicit_senior_dev, weak_inferred, "Senior Software Engineer"
    )
    # Coverage stays at 4/9 (low conf didn't unlock) BUT overclaim penalty
    # fires (avg conf 0.4 ≤ threshold). Score = 44.4 − 11.1 ≈ 33.3.
    assert abs(b.skills_depth - 33.3) < 0.2


def test_skills_coverage_overclaim_penalty_caveat_ratio(explicit_senior_dev):
    """Caveat ratio > 50% triggers overclaim penalty even with good conf."""
    caveat_heavy = InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="x",
                evidence_quote="ev1",
                confidence=0.8,
                relevance="must_have",
                caveat="led ≠ sole owner",
            ),
            SkillEvidence(
                skill="y",
                evidence_quote="ev2",
                confidence=0.8,
                relevance="must_have",
                caveat="peak metric, not current",
            ),
            SkillEvidence(
                skill="z",
                evidence_quote="ev3",
                confidence=0.8,
                relevance="nice_to_have",
            ),
        ]
    )
    b = components.compute_with_inferred(
        explicit_senior_dev, caveat_heavy, "Senior Software Engineer"
    )
    # 2/3 caveats > 0.5 threshold → penalty fires. 4/9 = 44.4, − 11.1 ≈ 33.3.
    assert abs(b.skills_depth - 33.3) < 0.2


def test_components_senior_dev_full(explicit_senior_dev, inferred_senior_dev):
    """senior_dev fixture under category-coverage methodology (9 cats):
    - Years: 8/15*100 ≈ 53
    - Skills coverage: 4 explicit categories + 1 inferred (aws → cloud_platform)
      = 5/9 ≈ 55.6 %. No overclaim penalty (1/3 caveats, avg conf 0.8).
    - Role: senior signal + 8 years (no +5 since <10) = 80
    - Education: master 50 + ČVUT prestige 5 + CS match +5 = 60
    """
    b = components.compute_with_inferred(
        explicit_senior_dev, inferred_senior_dev, "Senior Software Engineer"
    )
    assert 50 <= b.years_experience <= 55
    assert abs(b.skills_depth - 55.6) < 0.2
    assert b.role_progression == 80.0
    assert b.education == 60.0


def test_components_junior_support(explicit_junior_support, inferred_empty):
    """IT Support Specialist role family → unknown → LLM-based coverage
    scorer (autouse fixture returns 50 % default).
    Education: bachelor 30 + VŠE prestige 5 + unknown field family → 35."""
    b = components.compute_with_inferred(
        explicit_junior_support, inferred_empty, "IT Support Specialist"
    )
    assert 5 <= b.years_experience <= 8
    assert b.skills_depth == 50.0  # autouse stub returns 50 %
    assert b.role_progression == 25.0
    assert b.education == 35.0


def test_skills_coverage_unknown_skill_tech_role_no_credit(explicit_senior_dev, inferred_empty):
    """For tech roles, skills outside TECH_STACK_CATEGORIES don't count.
    "some-niche-tool" matches no category → 0% coverage."""
    explicit_senior_dev.explicit_skills = ["some-niche-tool"]
    b = components.compute_with_inferred(
        explicit_senior_dev, inferred_empty, "Senior Software Engineer"
    )
    assert b.skills_depth == 0.0


def test_skills_coverage_full_stack_saturates(explicit_senior_dev, inferred_empty):
    """CV listing skills covering all 9 categories saturates at 100%."""
    explicit_senior_dev.explicit_skills = [
        "python",  # language
        "postgres",  # database
        "aws",  # cloud_platform
        "kubernetes",  # container_orchestration
        "kafka",  # messaging_streaming
        "fastapi",  # framework_web
        "prometheus",  # observability
        "git",  # ci_devops
        "pytorch",  # ml_data_science
    ]
    b = components.compute_with_inferred(
        explicit_senior_dev, inferred_empty, "Senior Software Engineer"
    )
    assert b.skills_depth == 100.0


def test_skills_coverage_non_tech_uses_llm():
    """Non-tech roles (marketing/legal/sales/healthcare/business_mgmt)
    route through LLM-based coverage scoring. Verify the helper is
    invoked and its output reaches the score."""
    from cv_estimator.extractors.explicit import ExplicitData

    marketing_cv = ExplicitData(
        role="Marketing Manager",
        role_seniority_signal="senior",
        years_experience=6,
        explicit_skills=["google analytics", "seo", "hubspot", "content strategy"],
        highest_education="master",
        institution="VŠE",
        field_of_study="Marketing",
        language="en",
    )
    with patch(
        "cv_estimator.llm.call_json",
        return_value={
            "coverage_percent": 72,
            "missing_core": ["paid acquisition"],
            "value_adding_capabilities": ["google analytics"],
            "concerns": [],
        },
    ) as mock_call:
        b = components.compute_explicit_only(marketing_cv, "Marketing Manager")
    assert b.skills_depth == 72.0
    assert mock_call.call_count == 1


def test_coverage_attribution_for_non_tech():
    """For a non-tech role, `coverage_attribution_for` returns the LLM's
    value_adding / concerns lists. For tech roles, it returns None."""
    from cv_estimator.extractors.inferred import InferredData

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
        attr = components.coverage_attribution_for(
            "Marketing Manager",
            ["seo", "hubspot"],
            inferred.inferred_capabilities,
            include_inferred=True,
        )
    assert attr is not None
    assert attr.value_adding == ["seo"]
    assert attr.concerns == ["hubspot"]

    # Tech role → no attribution
    attr_tech = components.coverage_attribution_for(
        "Senior Backend Engineer", ["python"], [], include_inferred=False
    )
    assert attr_tech is None


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
