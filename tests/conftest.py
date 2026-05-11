"""Shared pytest fixtures."""

import pytest

from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import SkillEvidence


@pytest.fixture
def explicit_senior_dev() -> ExplicitData:
    return ExplicitData(
        role="Senior Software Engineer",
        role_seniority_signal="senior",
        years_experience=8,
        explicit_skills=["python", "kubernetes", "postgres", "kafka", "terraform"],
        highest_education="master",
        institution="ČVUT",
        field_of_study="Computer Science",
        language="en",
    )


@pytest.fixture
def inferred_senior_dev() -> InferredData:
    return InferredData(
        inferred_capabilities=[
            SkillEvidence(
                skill="technical leadership",
                evidence_quote="led migration of legacy system to cloud",
                confidence=0.85,
                relevance="must_have",
            ),
            SkillEvidence(
                skill="stakeholder management",
                evidence_quote="reported weekly to 200 stakeholders",
                confidence=0.75,
                relevance="nice_to_have",
            ),
        ]
    )


@pytest.fixture
def explicit_junior_support() -> ExplicitData:
    return ExplicitData(
        role="IT Support Specialist",
        role_seniority_signal="junior",
        years_experience=1,
        explicit_skills=["excel", "outlook", "jira"],
        highest_education="bachelor",
        institution="VŠE",
        field_of_study="Information Systems",
        language="cs",
    )


@pytest.fixture
def inferred_empty() -> InferredData:
    return InferredData(inferred_capabilities=[])
