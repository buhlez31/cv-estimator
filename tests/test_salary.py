"""Unit tests for salary/role_mapping.py and salary/lookup.py."""

from unittest.mock import patch

import pytest

from cv_estimator.salary import lookup, role_mapping


@pytest.fixture(autouse=True)
def _clear_llm_fallback_cache():
    """LLM fallback caches per role string via lru_cache. Clear between
    tests so mocked responses from one case don't leak into the next."""
    role_mapping._llm_fallback.cache_clear()
    yield
    role_mapping._llm_fallback.cache_clear()


@pytest.mark.parametrize(
    "role,expected_code",
    [
        # Tech
        ("Senior Software Engineer", "2512"),
        ("Software Developer", "2512"),
        ("Data Scientist", "2519"),
        ("Machine Learning Engineer", "2519"),
        ("Frontend Developer", "2513"),
        ("DevOps Engineer", "2523"),
        ("Database Administrator", "2521"),
        ("IT Support Specialist", "3512"),
        # C-suite
        ("CTO", "1330"),
        ("Head of IT", "1330"),
        ("CEO", "1120"),
        ("Managing Director", "1120"),
        ("CFO", "1211"),
        ("Head of Marketing", "1221"),
        # Mid management
        ("Marketing Manager", "1221"),
        ("Sales Manager", "1221"),
        ("HR Manager", "1212"),
        ("Finance Manager", "1211"),
        # Non-tech professionals
        ("Lawyer", "2611"),
        ("Legal Counsel", "2611"),
        ("Accountant", "2411"),
        ("Financial Analyst", "2411"),
        ("Recruiter", "2423"),
        ("Marketing Specialist", "2431"),
        ("Doctor", "2211"),
        ("Registered Nurse", "2221"),
        ("Pharmacist", "2262"),
        ("Teacher", "2330"),
        ("UX Designer", "2166"),
        ("Customer Success Manager", "4222"),
        ("Paralegal", "3411"),
        # Generic Czech catch-alls (prio 45 — fire when no specific rule matches)
        ("Analytik", "2511"),
        ("Manažer", "1219"),
        ("Vývojář", "2512"),
        ("Specialista", "2422"),
        ("Konzultant", "2422"),
        ("Ředitel", "1120"),
        # Plain English "analyst" (no domain) → same catch-all
        ("Analyst", "2511"),
    ],
)
def test_role_mapping(role, expected_code):
    assert role_mapping.map_to_cz_isco(role) == expected_code


def test_role_mapping_llm_fallback_success():
    """Unknown role triggers LLM fallback; LLM returns a valid code."""
    with patch("cv_estimator.llm.call_json", return_value={"code": "2111"}) as mock_call:
        result = role_mapping.map_to_cz_isco("Quantum Computing Researcher")
    assert result == "2111"
    assert mock_call.call_count == 1


def test_role_mapping_llm_fallback_unmatched_raises():
    """LLM returns UNMATCHED → UnmappedRoleError, caller surfaces to UI."""
    with patch("cv_estimator.llm.call_json", return_value={"code": "UNMATCHED"}):
        with pytest.raises(role_mapping.UnmappedRoleError) as exc_info:
            role_mapping.map_to_cz_isco("Completely Fictional Title")
    assert exc_info.value.role == "Completely Fictional Title"


def test_role_mapping_llm_fallback_invalid_code_raises():
    """LLM hallucinates a code not in the CSV → treated as unmapped."""
    with patch("cv_estimator.llm.call_json", return_value={"code": "9999"}):
        with pytest.raises(role_mapping.UnmappedRoleError):
            role_mapping.map_to_cz_isco("Another Fictional Title")


def test_role_mapping_llm_fallback_caches_per_role():
    """Same unmapped role hit twice → LLM called once (lru_cache)."""
    with patch("cv_estimator.llm.call_json", return_value={"code": "2511"}) as mock_call:
        a = role_mapping.map_to_cz_isco("Niche Title For Cache Test")
        b = role_mapping.map_to_cz_isco("Niche Title For Cache Test")
    assert a == b == "2511"
    assert mock_call.call_count == 1


def test_role_mapping_keyword_match_skips_llm():
    """Known role (matches keyword rule) → LLM never called."""
    with patch("cv_estimator.llm.call_json") as mock_call:
        result = role_mapping.map_to_cz_isco("Senior Backend Engineer")
    assert result == "2512"
    assert mock_call.call_count == 0


def test_role_mapping_empty_string_raises():
    with pytest.raises(role_mapping.UnmappedRoleError):
        role_mapping.map_to_cz_isco("")


def test_salary_score_70_lands_at_p50():
    """Bucket boundary: score 70 = start of "senior" bucket = exactly P50."""
    est = lookup.estimate_salary("2512", 70)
    assert est.median == 101_103
    assert est.percentile_position == 50


def test_salary_junior_bucket_caps_at_p25():
    """Score 0-40 = junior bucket → median pinned at P25, percentile 25."""
    est = lookup.estimate_salary("2512", 20)
    assert est.median == 71_536  # P25 for 2512
    assert est.percentile_position == 25


def test_salary_mid_bucket_between_p25_and_p50():
    """Score 40-70 interpolates between P25 and P50."""
    est = lookup.estimate_salary("2512", 55)
    # Fraction (55-40)/(70-40) = 0.5 → median = 71536 + 0.5*(101103-71536) = 86319
    assert 80_000 < est.median < 95_000
    assert 25 <= est.percentile_position <= 50


def test_salary_higher_score_higher_median():
    low = lookup.estimate_salary("2512", 25).median
    mid = lookup.estimate_salary("2512", 55).median
    senior = lookup.estimate_salary("2512", 80).median
    principal = lookup.estimate_salary("2512", 95).median
    assert low < mid < senior < principal


def test_salary_range_ordering():
    est = lookup.estimate_salary("2512", 75)
    assert est.low <= est.median <= est.high


def test_salary_unknown_code_falls_back():
    est = lookup.estimate_salary("9999", 70)
    # Should fall back to 2519 default; just check returns a valid estimate
    assert est.low > 0
    assert est.percentile_position == 50


def test_salary_prefix_fallback():
    # 2515 doesn't exist in CSV but 251x prefix has 2511, 2512, 2513, 2514
    est = lookup.estimate_salary("2515", 50)
    assert est.median > 0


def test_salary_exposes_market_band():
    """Salary estimate must include the full ISPV P25-P90 band so the UI
    can render the candidate's position within the market range."""
    est = lookup.estimate_salary("2512", 50)
    assert est.market_p25 == 71_536
    assert est.market_p50 == 101_103
    assert est.market_p75 == 141_956
    assert est.market_p90 == 184_858
    assert est.market_p25 < est.market_p50 < est.market_p75 < est.market_p90
