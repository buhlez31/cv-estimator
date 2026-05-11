"""End-to-end pipeline test with mocked LLM calls.

Skips the real Anthropic API; verifies that the orchestrator wires the
domain modules together correctly and produces a valid CVAnalysis with
both parallel tracks populated.
"""

from unittest.mock import patch

from cv_estimator import pipeline
from cv_estimator.models import CVAnalysis

SAMPLE_TXT = b"""John Doe
Senior Data Engineer

Experience
- Built and maintained ETL pipelines processing 500M events/day in Python and SQL.
- Led migration of legacy reporting system to Snowflake; reduced query latency by 60%.
- Mentored 3 junior engineers and ran the weekly team retro.

Skills: python, sql, snowflake, kafka, airflow, dbt, git

Education
- M.Sc. Computer Science, Charles University, 2016
"""


def _mock_call_json(prompt: str) -> dict:
    """Dispatch a deterministic JSON payload based on which prompt is being rendered."""
    if "Extract explicit CV facts" in prompt:
        return {
            "role": "Senior Data Engineer",
            "role_seniority_signal": "senior",
            "years_experience": 9,
            "explicit_skills": ["python", "sql", "snowflake", "kafka", "airflow", "dbt", "git"],
            "highest_education": "master",
            "institution": "Charles University",
            "field_of_study": "Computer Science",
            "language": "en",
        }
    if "Extract inferred capabilities" in prompt:
        return {
            "inferred_capabilities": [
                {
                    "skill": "data engineering",
                    "evidence_quote": "Built and maintained ETL pipelines processing 500M events/day",
                    "confidence": 0.7,
                    "relevance": "must_have",
                    "caveat": None,
                },
                {
                    "skill": "technical leadership",
                    "evidence_quote": "Led migration of legacy reporting system to Snowflake",
                    "confidence": 0.55,
                    "relevance": "nice_to_have",
                    "caveat": "led ≠ sole architect",
                },
                {
                    "skill": "mentoring",
                    "evidence_quote": "Mentored 3 junior engineers",
                    "confidence": 0.75,
                    "relevance": "nice_to_have",
                    "caveat": None,
                },
            ]
        }
    if "Strengths & gaps analysis" in prompt:
        return {
            "strengths": [
                "Strong production data-engineering scope (500M events/day).",
                "Demonstrated leadership via migration and mentoring.",
                "Solid modern data stack (Snowflake, dbt, Airflow).",
            ],
            "gaps": [
                "No explicit cloud certification.",
                "No people-management title yet.",
                "No streaming-architecture deep dive shown.",
            ],
        }
    if "Salary growth roadmap" in prompt:
        return {
            "recommendations": [
                {
                    "action": "Obtain AWS Solutions Architect Professional certification",
                    "time_investment": "3-6 months",
                    "expected_impact": "Boosts skills_depth and unlocks senior cloud roles, +10-15% salary band.",
                    "target_skill": "cloud architecture",
                },
                {
                    "action": "Lead a real-time streaming project end-to-end (Kafka Streams + Flink)",
                    "time_investment": "6-12 months",
                    "expected_impact": "Demonstrates streaming expertise, shifts to higher CZ-ISCO band.",
                    "target_skill": "streaming architecture",
                },
                {
                    "action": "Take on a team-lead role for 4+ engineers within current employer",
                    "time_investment": "12-18 months",
                    "expected_impact": "Moves role_progression toward principal/manager tier (+30% pay band).",
                    "target_skill": "people management",
                },
            ]
        }
    if "Target role match assessment" in prompt:
        return {
            "match_score": 72,
            "rationale": (
                "Strong data engineering and migration scope are a clear strength; "
                "gap is people-management experience for a manager track."
            ),
        }
    if "Skills coverage scoring for non-tech role" in prompt:
        # CTO target → business_mgmt family → LLM coverage scoring path.
        return {"coverage_percent": 55, "missing_core": ["budget management"]}
    raise AssertionError(f"Unexpected prompt: {prompt[:100]}")


def test_pipeline_end_to_end():
    """No target_role → analysis anchored on detected role, no match panel."""
    with patch("cv_estimator.llm.call_json", side_effect=_mock_call_json):
        result = pipeline.analyze_cv(SAMPLE_TXT, "sample.txt")

    assert isinstance(result, CVAnalysis)
    assert result.detected_role == "Senior Data Engineer"
    assert result.analysis_role == "Senior Data Engineer"
    assert result.role_source == "detected"
    assert result.cz_isco_code == "2519"
    assert result.language == "en"
    # No target supplied → no LLM #5
    assert result.target is None
    assert result.processing_metadata["target_role_provided"] is False

    # Both parallel tracks populated.
    assert 0 <= result.track_explicit.seniority_score <= 100
    assert 0 <= result.track_with_inferred.seniority_score <= 100
    assert result.track_with_inferred.seniority_score >= result.track_explicit.seniority_score

    for track in (result.track_explicit, result.track_with_inferred):
        s = track.salary_estimate
        assert s.low <= s.median <= s.high
        assert s.market_p25 < s.market_p50 < s.market_p75 < s.market_p90

    assert len(result.recommendations) == 3
    assert 3 <= len(result.strengths) <= 5
    assert 3 <= len(result.gaps) <= 5

    # Hidden assets carry caveat strings or None.
    caveats = [c.caveat for c in result.inferred_capabilities]
    assert any(c is not None for c in caveats)


def test_pipeline_with_target_role_drives_everything():
    """target_role supplied → analysis anchored on target, match panel populated,
    salary uses target's CZ-ISCO band, NOT detected."""
    with patch("cv_estimator.llm.call_json", side_effect=_mock_call_json):
        result = pipeline.analyze_cv(SAMPLE_TXT, "sample.txt", target_role="CTO")

    # detected_role unchanged for traceability — but analysis is anchored on
    # the target.
    assert result.detected_role == "Senior Data Engineer"
    assert result.analysis_role == "CTO"
    assert result.role_source == "target"
    # "CTO" maps to CZ-ISCO 1330; detected "Data Engineer" would map to 2519.
    assert result.cz_isco_code == "1330"

    # LLM #5 ran.
    assert result.target is not None
    assert result.target.target_role == "CTO"
    assert result.target.target_cz_isco == "1330"
    assert result.target.match_score == 72
    assert result.processing_metadata["target_role_provided"] is True

    # Salary anchored on CTO (1330) band — median for 1330 P50 ≈ 148k CZK,
    # far above the 2519 P50 (~83k).
    assert result.track_with_inferred.salary_estimate.median > 120_000
    assert result.track_explicit.salary_estimate.market_p50 > 120_000
