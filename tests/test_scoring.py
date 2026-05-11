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


def test_components_explicit_only_capped_at_75(explicit_senior_dev):
    """Buzzword baseline is capped at 75 even when raw skill-tier sum exceeds it.

    senior_dev fixture: kubernetes+terraform (high, 25+25=50) + python+postgres+
    kafka (mid, 15+15+15=45) → raw 95 → clamped to 75. This is the mechanism
    that makes the two tracks visibly diverge in the UI.
    """
    b_explicit = components.compute_explicit_only(explicit_senior_dev)
    assert b_explicit.skills_depth == 75.0


def test_components_with_inferred_exceeds_baseline(explicit_senior_dev, inferred_senior_dev):
    """With-inferred track must score strictly higher when inferred caps exist."""
    b_explicit = components.compute_explicit_only(explicit_senior_dev)
    b_full = components.compute_with_inferred(explicit_senior_dev, inferred_senior_dev)
    assert b_full.skills_depth > b_explicit.skills_depth


def test_inferred_bonus_is_confidence_weighted(explicit_junior_support):
    """A 0.4-confidence capability contributes 40 % of what 1.0 does
    (multiplier 8 per capability, capped at 25 aggregate). must_have
    relevance contributes full weight; nice_to_have contributes half."""
    from cv_estimator.extractors.inferred import InferredData
    from cv_estimator.models import SkillEvidence

    must_weak = InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="x",
                evidence_quote="ev1",
                confidence=0.4,
                relevance="must_have",
            ),
        ]
    )
    must_strong = InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="y",
                evidence_quote="ev2",
                confidence=1.0,
                relevance="must_have",
            ),
        ]
    )
    nice_strong = InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="z",
                evidence_quote="ev3",
                confidence=1.0,
                relevance="nice_to_have",
            ),
        ]
    )
    explicit_at_100 = components._explicit_skills_score(
        explicit_junior_support.explicit_skills, cap=100.0
    )
    b_must_weak = components.compute_with_inferred(explicit_junior_support, must_weak)
    b_must_strong = components.compute_with_inferred(explicit_junior_support, must_strong)
    b_nice_strong = components.compute_with_inferred(explicit_junior_support, nice_strong)
    # must_have, 0.4 conf × 8 = 3.2
    assert abs(b_must_weak.skills_depth - (explicit_at_100 + 3.2)) < 0.01
    # must_have, 1.0 conf × 8 = 8.0
    assert abs(b_must_strong.skills_depth - (explicit_at_100 + 8.0)) < 0.01
    # nice_to_have, 1.0 conf × 8 × 0.5 = 4.0
    assert abs(b_nice_strong.skills_depth - (explicit_at_100 + 4.0)) < 0.01


def test_components_senior_dev_full(explicit_senior_dev, inferred_senior_dev):
    """senior_dev fixture: explicit @ cap-100 = 95, inferred bonus
    (0.85+0.75)*8 = 12.8 → 107.8 clamped to 100."""
    b = components.compute_with_inferred(explicit_senior_dev, inferred_senior_dev)
    # 8/15*100 ≈ 53
    assert 50 <= b.years_experience <= 55
    # explicit 95 + bonus 12.8 = 107.8 → clamped to 100
    assert b.skills_depth == 100.0
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
