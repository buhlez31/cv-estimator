"""Thin orchestrator — sequences the 4 LLM passes + scoring + salary lookup.

Per the design doc: this file is a table of contents, NOT a place for logic.
Each step is a single call into a domain module.
"""

import time

from cv_estimator.explanation import narrative, roadmap
from cv_estimator.extractors import document, explicit, inferred
from cv_estimator.models import CVAnalysis
from cv_estimator.salary import lookup, role_mapping
from cv_estimator.scoring import components, seniority
from cv_estimator.validation import sanity


def analyze_cv(file_bytes: bytes, filename: str) -> CVAnalysis:
    """Run the full pipeline. Returns a validated CVAnalysis."""
    started = time.time()

    raw_text = document.extract_text(file_bytes, filename)
    language = document.detect_language(raw_text)

    explicit_data = explicit.extract(raw_text, language)
    inferred_data = inferred.extract(raw_text, language)
    cz_isco = role_mapping.map_to_cz_isco(explicit_data.role)

    breakdown = components.compute(explicit_data, inferred_data)
    score = seniority.compute(breakdown)
    salary = lookup.estimate_salary(cz_isco, score)

    sg = narrative.analyze(explicit_data, inferred_data, breakdown, score)
    recs = roadmap.generate(explicit_data, sg.gaps, score, cz_isco)

    result = CVAnalysis(
        detected_role=explicit_data.role,
        cz_isco_code=cz_isco,
        role_confidence=1.0 if cz_isco != "2519" else 0.6,
        language=explicit_data.language,
        seniority_score=score,
        breakdown=breakdown,
        explicit_skills=explicit_data.explicit_skills,
        inferred_capabilities=inferred_data.inferred_capabilities,
        salary_estimate=salary,
        strengths=sg.strengths,
        gaps=sg.gaps,
        recommendations=recs,
        processing_metadata={
            "filename": filename,
            "elapsed_seconds": round(time.time() - started, 2),
            "raw_text_chars": len(raw_text),
        },
    )
    sanity.validate(result)
    return result
