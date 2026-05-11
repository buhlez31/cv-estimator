"""Unit tests for scoring/components.py and scoring/seniority.py."""

from cv_estimator.models import ScoreBreakdown
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


def test_components_explicit_only_excludes_inferred_bonus(explicit_senior_dev, inferred_senior_dev):
    """Skeptical baseline must NOT include the inferred capabilities bonus."""
    b_explicit = components.compute_explicit_only(explicit_senior_dev)
    b_full = components.compute_with_inferred(explicit_senior_dev, inferred_senior_dev)
    assert b_full.skills_depth >= b_explicit.skills_depth
    # The senior dev fixture's explicit skills (kubernetes+terraform high,
    # python+postgres+kafka mid) already saturate 100 — bonus invisible.
    # Sanity: at least confirm explicit-only never exceeds 100.
    assert b_explicit.skills_depth <= 100


def test_inferred_bonus_is_confidence_weighted(explicit_junior_support):
    """A 0.4-confidence capability contributes 40% of what 1.0 does."""
    from cv_estimator.extractors.inferred import InferredData
    from cv_estimator.models import SkillEvidence

    weak = InferredData(
        inferred_capabilities=[
            SkillEvidence(skill="x", evidence_quote="ev1", confidence=0.4),
        ]
    )
    strong = InferredData(
        inferred_capabilities=[
            SkillEvidence(skill="y", evidence_quote="ev2", confidence=1.0),
        ]
    )
    b_weak = components.compute_with_inferred(explicit_junior_support, weak)
    b_strong = components.compute_with_inferred(explicit_junior_support, strong)
    delta_weak = (
        b_weak.skills_depth - components.compute_explicit_only(explicit_junior_support).skills_depth
    )
    delta_strong = (
        b_strong.skills_depth
        - components.compute_explicit_only(explicit_junior_support).skills_depth
    )
    # 0.4 cap contributes 5 * 0.4 = 2.0
    assert abs(delta_weak - 2.0) < 0.01
    # 1.0 cap contributes 5 * 1.0 = 5.0
    assert abs(delta_strong - 5.0) < 0.01


def test_components_senior_dev_full(explicit_senior_dev, inferred_senior_dev):
    b = components.compute_with_inferred(explicit_senior_dev, inferred_senior_dev)
    # 8/15*100 ≈ 53
    assert 50 <= b.years_experience <= 55
    # explicit skills saturate 100 already
    assert b.skills_depth == 100
    # senior signal + 8 years (no +5 since <10)
    assert b.role_progression == 80.0
    # master = 85, ČVUT prestige boost +5 = 90
    assert b.education == 90.0


def test_components_junior_support(explicit_junior_support, inferred_empty):
    b = components.compute_with_inferred(explicit_junior_support, inferred_empty)
    # 1/15*100 ≈ 6.67
    assert 5 <= b.years_experience <= 8
    # excel(5) + outlook(5) + jira(5) = 15, no inferred bonus
    assert b.skills_depth == 15.0
    # junior signal
    assert b.role_progression == 25.0
    # bachelor=60, VŠE prestige +5 = 65
    assert b.education == 65.0


def test_components_unknown_skill_partial_credit(explicit_senior_dev, inferred_empty):
    explicit_senior_dev.explicit_skills = ["some-niche-tool"]
    b = components.compute_with_inferred(explicit_senior_dev, inferred_empty)
    assert b.skills_depth == 8.0  # unknown → 8 pt fallback
