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


def test_components_senior_dev(explicit_senior_dev, inferred_senior_dev):
    b = components.compute(explicit_senior_dev, inferred_senior_dev)
    # 8/15*100 ≈ 53
    assert 50 <= b.years_experience <= 55
    # high-tier skills (kubernetes, terraform) + mid (python, postgres, kafka)
    # = 25+25 + 15+15+15 = 95, +10 inferred bonus → capped 100
    assert b.skills_depth == 100
    # senior signal + 8 years (no +5 since <10)
    assert b.role_progression == 80.0
    # master = 85, ČVUT prestige boost +5 = 90
    assert b.education == 90.0


def test_components_junior_support(explicit_junior_support, inferred_empty):
    b = components.compute(explicit_junior_support, inferred_empty)
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
    b = components.compute(explicit_senior_dev, inferred_empty)
    assert b.skills_depth == 8.0  # unknown → 8 pt fallback
