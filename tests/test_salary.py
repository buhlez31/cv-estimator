"""Unit tests for salary/role_mapping.py and salary/lookup.py."""

import pytest

from cv_estimator.salary import lookup, role_mapping


@pytest.mark.parametrize(
    "role,expected_code",
    [
        ("Senior Software Engineer", "2512"),
        ("Software Developer", "2512"),
        ("Data Scientist", "2519"),
        ("Machine Learning Engineer", "2519"),
        ("Frontend Developer", "2513"),
        ("DevOps Engineer", "2523"),
        ("Database Administrator", "2521"),
        ("IT Support Specialist", "3512"),
        ("CTO", "1330"),
        ("Head of IT", "1330"),
        ("Random Title", "2519"),  # fallback
    ],
)
def test_role_mapping(role, expected_code):
    assert role_mapping.map_to_cz_isco(role) == expected_code


def test_role_mapping_empty_string():
    assert role_mapping.map_to_cz_isco("") == "2519"


def test_salary_p50_matches_score_50():
    est = lookup.estimate_salary("2512", 50)
    # P50 from ISPV 2025 CSV for 2512 (Software developer, MZDOVA) is 101103 CZK.
    assert est.median == 101_103
    assert est.percentile_position == 50


def test_salary_higher_score_higher_median():
    low = lookup.estimate_salary("2512", 25).median
    mid = lookup.estimate_salary("2512", 50).median
    high = lookup.estimate_salary("2512", 90).median
    assert low < mid < high


def test_salary_range_ordering():
    est = lookup.estimate_salary("2512", 75)
    assert est.low <= est.median <= est.high


def test_salary_unknown_code_falls_back():
    est = lookup.estimate_salary("9999", 50)
    # Should fall back to 2519 default; just check returns a valid estimate
    assert est.low > 0
    assert est.percentile_position == 50


def test_salary_prefix_fallback():
    # 2515 doesn't exist in CSV but 251x prefix has 2511, 2512, 2513, 2514
    est = lookup.estimate_salary("2515", 50)
    assert est.median > 0
