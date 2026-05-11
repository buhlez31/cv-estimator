"""End-to-end pipeline test with mocked LLM calls.

Skips the real Anthropic API; verifies that the orchestrator wires the
domain modules together correctly and produces a valid CVAnalysis.
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
            "language": "en",
        }
    if "Extract inferred capabilities" in prompt:
        return {
            "inferred_capabilities": [
                {
                    "skill": "data engineering",
                    "evidence_quote": "Built and maintained ETL pipelines processing 500M events/day",
                    "confidence": 0.95,
                },
                {
                    "skill": "technical leadership",
                    "evidence_quote": "Led migration of legacy reporting system to Snowflake",
                    "confidence": 0.85,
                },
                {
                    "skill": "mentoring",
                    "evidence_quote": "Mentored 3 junior engineers",
                    "confidence": 0.8,
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
    raise AssertionError(f"Unexpected prompt: {prompt[:100]}")


def test_pipeline_end_to_end():
    with patch("cv_estimator.llm.call_json", side_effect=_mock_call_json):
        result = pipeline.analyze_cv(SAMPLE_TXT, "sample.txt")

    assert isinstance(result, CVAnalysis)
    assert result.detected_role == "Senior Data Engineer"
    assert result.cz_isco_code == "2519"  # "Data Engineer" → 2519 per rules
    assert result.language == "en"
    assert 0 <= result.seniority_score <= 100
    assert len(result.recommendations) == 3
    assert 3 <= len(result.strengths) <= 5
    assert 3 <= len(result.gaps) <= 5
    assert (
        result.salary_estimate.low <= result.salary_estimate.median <= result.salary_estimate.high
    )
    # Senior with strong skills should land at a respectable score
    assert result.seniority_score >= 60
