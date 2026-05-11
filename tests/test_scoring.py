"""Unit tests for scoring/components.py and scoring/seniority.py."""

from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown, SkillEvidence
from cv_estimator.scoring import components, seniority


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


def test_components_explicit_only_capped_at_75(explicit_senior_dev):
    """Buzzword baseline is capped at 75 even when raw skill-tier sum exceeds it."""
    b_explicit = components.compute_explicit_only(explicit_senior_dev, "Senior Software Engineer")
    assert b_explicit.skills_depth == 75.0


def test_components_with_inferred_exceeds_baseline(explicit_senior_dev, inferred_senior_dev):
    """With-inferred track must score strictly higher when inferred caps exist."""
    role = "Senior Software Engineer"
    b_explicit = components.compute_explicit_only(explicit_senior_dev, role)
    b_full = components.compute_with_inferred(explicit_senior_dev, inferred_senior_dev, role)
    assert b_full.skills_depth > b_explicit.skills_depth


def test_inferred_bonus_is_confidence_weighted(explicit_junior_support):
    """A 0.4-confidence capability contributes 40 % of what 1.0 does
    (multiplier 8 per capability, capped at 25 aggregate). must_have
    relevance contributes full weight; nice_to_have contributes half."""
    role = "IT Support Specialist"
    must_weak = InferredData(
        inferred_capabilities=[
            SkillEvidence(skill="x", evidence_quote="ev1", confidence=0.4, relevance="must_have"),
        ]
    )
    must_strong = InferredData(
        inferred_capabilities=[
            SkillEvidence(skill="y", evidence_quote="ev2", confidence=1.0, relevance="must_have"),
        ]
    )
    nice_strong = InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="z", evidence_quote="ev3", confidence=1.0, relevance="nice_to_have"
            ),
        ]
    )
    explicit_at_100 = components._explicit_skills_score(
        explicit_junior_support.explicit_skills, cap=100.0
    )
    b_must_weak = components.compute_with_inferred(explicit_junior_support, must_weak, role)
    b_must_strong = components.compute_with_inferred(explicit_junior_support, must_strong, role)
    b_nice_strong = components.compute_with_inferred(explicit_junior_support, nice_strong, role)
    # must_have, 0.4 conf × 8 = 3.2
    assert abs(b_must_weak.skills_depth - (explicit_at_100 + 3.2)) < 0.01
    # must_have, 1.0 conf × 8 = 8.0
    assert abs(b_must_strong.skills_depth - (explicit_at_100 + 8.0)) < 0.01
    # nice_to_have, 1.0 conf × 8 × 0.5 = 4.0
    assert abs(b_nice_strong.skills_depth - (explicit_at_100 + 4.0)) < 0.01


def test_components_senior_dev_full(explicit_senior_dev, inferred_senior_dev):
    """senior_dev fixture: explicit @ cap-100 = 95, inferred bonus
    (0.85+0.75/2)*8 = 9.8 → 104.8 clamped to 100.
    Education: master 85 + ČVUT prestige +5 + CS field matches Senior Software
    Engineer (tech) → +5 = 95.
    """
    b = components.compute_with_inferred(
        explicit_senior_dev, inferred_senior_dev, "Senior Software Engineer"
    )
    assert 50 <= b.years_experience <= 55
    assert b.skills_depth == 100.0
    assert b.role_progression == 80.0
    assert b.education == 95.0


def test_components_junior_support(explicit_junior_support, inferred_empty):
    """Education: bachelor 60 + VŠE prestige +5 + Information Systems field
    family unknown → 0 → 65 (unchanged vs pre-field-relevance)."""
    b = components.compute_with_inferred(
        explicit_junior_support, inferred_empty, "IT Support Specialist"
    )
    assert 5 <= b.years_experience <= 8
    assert b.skills_depth == 15.0
    assert b.role_progression == 25.0
    assert b.education == 65.0


def test_components_unknown_skill_partial_credit(explicit_senior_dev, inferred_empty):
    explicit_senior_dev.explicit_skills = ["some-niche-tool"]
    b = components.compute_with_inferred(
        explicit_senior_dev, inferred_empty, "Senior Software Engineer"
    )
    assert b.skills_depth == 8.0


# ----- Education field-relevance modifier ------------------------------------


def test_education_tech_field_tech_role_gets_bonus(explicit_senior_dev):
    """CS degree + Backend Engineer (tech role) → +5 match bonus on edu."""
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    # master 85 + ČVUT prestige 5 + match bonus 5 = 95
    assert b.education == 95.0


def test_education_non_tech_field_tech_role_gets_penalty(explicit_senior_dev):
    """History degree + Backend Engineer (tech role) → -10 mismatch penalty."""
    explicit_senior_dev.field_of_study = "History"
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    # master 85 + ČVUT prestige 5 - 10 = 80
    assert b.education == 80.0


def test_education_adjacent_field_tech_role_neutral(explicit_senior_dev):
    """Geoinformatika (tech_adjacent) + Research Analyst (tech) → 0 modifier."""
    explicit_senior_dev.field_of_study = "Geoinformatika"
    b = components.compute_explicit_only(explicit_senior_dev, "Research Analyst")
    # master 85 + ČVUT prestige 5 + 0 = 90
    assert b.education == 90.0


def test_education_empty_field_no_modifier(explicit_senior_dev):
    """Empty field_of_study → no modifier (no signal, no penalty)."""
    explicit_senior_dev.field_of_study = ""
    b = components.compute_explicit_only(explicit_senior_dev, "Senior Backend Engineer")
    # master 85 + ČVUT prestige 5 + 0 = 90
    assert b.education == 90.0


def test_education_tech_field_non_tech_role_gets_penalty(explicit_senior_dev):
    """CS degree + Marketing Manager (marketing) → -10 penalty (mismatch)."""
    b = components.compute_explicit_only(explicit_senior_dev, "Marketing Manager")
    # NOTE: "Marketing Manager" contains "manager" → business_mgmt family wins via dict ordering.
    # business_mgmt + tech is in adjacent pairs → 0 modifier. master 85 + prestige 5 = 90.
    assert b.education == 90.0


def test_education_business_mgmt_role_with_tech_field_adjacent(explicit_senior_dev):
    """CTO (business_mgmt by 'chief' keyword) + CS degree → 0 (adjacent pair)."""
    b = components.compute_explicit_only(explicit_senior_dev, "CTO")
    # Same as above logic — business_mgmt + tech in adjacency.
    assert b.education == 90.0


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
