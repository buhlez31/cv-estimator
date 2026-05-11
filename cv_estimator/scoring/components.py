"""Compute the 4 ScoreBreakdown components from extractor outputs.

Two entry points produce two ScoreBreakdowns:

- `compute_explicit_only` — buzzword baseline using only literal CV content.
  Objective view — no skepticism applied here, just degree of skill listing.
- `compute_with_inferred` — adds a confidence-weighted bonus from the
  hidden-assets pass. The inferred extraction itself is the only part of
  the pipeline that applies skepticism.

The weighted aggregate is in `seniority.py`.
"""

from functools import lru_cache

from cv_estimator.config import (
    EDUCATION_BASE_MAP,
    EDUCATION_EMPTY_FIELD_MULTIPLIER,
    EDUCATION_FIELD_MATCH_BONUS,
    EDUCATION_FIELD_MISMATCH_PENALTY,
    EDUCATION_PRESTIGE_BONUS,
    FIELD_FAMILY_KEYWORDS,
    INFERRED_BONUS_CAP,
    INFERRED_BONUS_PER_CAPABILITY,
    INFERRED_COVERAGE_CONFIDENCE_THRESHOLD,
    JUNIOR_TITLE_KEYWORDS,
    OVERCLAIM_AVG_CONFIDENCE_THRESHOLD,
    OVERCLAIM_CAVEAT_RATIO_THRESHOLD,
    OVERCLAIM_PENALTY_POINTS,
    PRESTIGE_INSTITUTION_KEYWORDS,
    ROLE_FAMILY_KEYWORDS,
    ROLE_FIELD_ADJACENT_PAIRS,
    SENIOR_TITLE_KEYWORDS,
    SKILL_TIERS_HIGH,
    SKILL_TIERS_LOW,
    SKILL_TIERS_MID,
    TECH_STACK_CATEGORIES,
    YEARS_CAP,
)
from cv_estimator.extractors.explicit import ExplicitData
from cv_estimator.extractors.inferred import InferredData
from cv_estimator.models import ScoreBreakdown


def compute_explicit_only(explicit: ExplicitData, analysis_role: str) -> ScoreBreakdown:
    """Buzzword baseline — uses only what is literally in the CV.

    For technical roles, skills_depth is a **category coverage** score
    (covered TECH_STACK_CATEGORIES / total). For non-tech roles, falls
    back to the legacy tier-weighted scoring with the asymmetric cap.

    `analysis_role` drives both the skills category check and the
    education field-relevance modifier.
    """
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience),
        skills_depth=_skills_coverage_score(
            explicit.explicit_skills, [], analysis_role, include_inferred=False
        ),
        role_progression=_role_progression_score(
            explicit.role, explicit.role_seniority_signal, explicit.years_experience
        ),
        education=_education_score(
            explicit.highest_education,
            explicit.institution,
            explicit.field_of_study,
            analysis_role,
        ),
    )


def compute_with_inferred(
    explicit: ExplicitData,
    inferred: InferredData,
    analysis_role: str,
) -> ScoreBreakdown:
    """Hidden-assets-included view — for tech roles, inferred capabilities
    with confidence ≥ threshold can unlock additional stack categories.
    For non-tech roles, applies the legacy confidence-weighted bonus."""
    return ScoreBreakdown(
        years_experience=_years_score(explicit.years_experience),
        skills_depth=_skills_coverage_score(
            explicit.explicit_skills,
            inferred.inferred_capabilities,
            analysis_role,
            include_inferred=True,
        ),
        role_progression=_role_progression_score(
            explicit.role, explicit.role_seniority_signal, explicit.years_experience
        ),
        education=_education_score(
            explicit.highest_education,
            explicit.institution,
            explicit.field_of_study,
            analysis_role,
        ),
    )


# Backwards-compatible alias for any external caller — internal pipeline
# uses the two explicit entry points above.
def compute(
    explicit: ExplicitData,
    inferred: InferredData,
    analysis_role: str | None = None,
) -> ScoreBreakdown:
    return compute_with_inferred(explicit, inferred, analysis_role or explicit.role)


# ----- Internals ---------------------------------------------------------


def _years_score(years: int) -> float:
    """Continuous, capped at YEARS_CAP (15)."""
    return float(min(years, YEARS_CAP) / YEARS_CAP * 100)


def _skills_coverage_score(
    explicit_skills: list[str],
    inferred_capabilities: list,
    analysis_role: str,
    *,
    include_inferred: bool,
) -> float:
    """Category-coverage score for technical roles, tier-weighted fallback
    otherwise.

    Tech path: build a set of signal strings (explicit skills + optionally
    inferred capabilities meeting the confidence threshold), then count
    how many TECH_STACK_CATEGORIES are "covered" — i.e. at least one
    signal in the candidate's list matches at least one keyword in the
    category's set. Score = covered / total × 100.

    Non-tech path: fall back to the legacy tier-weighted sum, with the
    explicit-only cap if include_inferred=False, or +inferred bonus
    otherwise. We don't have calibrated category lists for non-tech
    role families.
    """
    role_family = _classify_role_family(analysis_role)

    if role_family == "tech":
        signals = {s.strip().lower() for s in explicit_skills if s.strip()}
        if include_inferred:
            for cap in inferred_capabilities:
                if cap.confidence >= INFERRED_COVERAGE_CONFIDENCE_THRESHOLD:
                    signals.add(cap.skill.strip().lower())

        covered = 0
        for keywords in TECH_STACK_CATEGORIES.values():
            if any(any(kw in s for kw in keywords) for s in signals):
                covered += 1
        score = (covered / len(TECH_STACK_CATEGORIES)) * 100.0

        # Overclaim penalty (with-inferred track only): if the inferred
        # pass returned a lot of caveats or low-confidence inferences,
        # the CV's claims may be overselling. Subtract a virtual-category
        # equivalent so the score can land BELOW the explicit baseline —
        # bidirectional methodology.
        if include_inferred and inferred_capabilities:
            n = len(inferred_capabilities)
            n_caveats = sum(1 for c in inferred_capabilities if c.caveat)
            avg_conf = sum(c.confidence for c in inferred_capabilities) / n
            overclaim = (
                n_caveats / n > OVERCLAIM_CAVEAT_RATIO_THRESHOLD
                or avg_conf <= OVERCLAIM_AVG_CONFIDENCE_THRESHOLD
            )
            if overclaim:
                score = max(0.0, score - OVERCLAIM_PENALTY_POINTS)
        return score

    # Non-tech roles: LLM-based coverage scoring. The tech-stack
    # checklist doesn't fit marketing / legal / sales / healthcare /
    # management. Use the model's knowledge of each role's expected
    # competencies.
    return _llm_coverage_nontech(
        analysis_role,
        tuple(s.strip().lower() for s in explicit_skills if s.strip()),
        (
            tuple(
                (c.skill.strip().lower(), round(c.confidence, 2))
                for c in inferred_capabilities
                if c.confidence >= INFERRED_COVERAGE_CONFIDENCE_THRESHOLD
            )
            if include_inferred
            else ()
        ),
        include_inferred=include_inferred,
    )


@lru_cache(maxsize=128)
def _llm_coverage_nontech(
    role: str,
    explicit_skills_tuple: tuple[str, ...],
    inferred_caps_tuple: tuple[tuple[str, float], ...],
    *,
    include_inferred: bool,
) -> float:
    """LLM-based skills coverage scoring for non-tech roles.

    Asks the model to estimate what percent of the role's expected core
    competencies the candidate's CV demonstrates. Cached per
    (role, skills, inferred, include_inferred) so the same analysis
    doesn't re-query.

    Lazy import of `llm` to keep test fixtures that exercise only tech
    paths from needing Anthropic client setup.
    """
    import json as _json

    from cv_estimator import llm

    inferred_payload = [{"skill": s, "confidence": c} for s, c in inferred_caps_tuple]
    prompt = llm.render_prompt(
        "skills_coverage_nontech",
        role=role,
        explicit_skills=_json.dumps(list(explicit_skills_tuple), ensure_ascii=False),
        inferred_capabilities=_json.dumps(inferred_payload, ensure_ascii=False),
    )
    payload = llm.call_json(prompt)
    score = float(payload.get("coverage_percent", 0) or 0)
    return max(0.0, min(100.0, score))


def _explicit_skills_score(skills: list[str], *, cap: float) -> float:
    """Tier-weighted score for skills that literally appear in the CV,
    clamped to the caller-supplied cap. The explicit-only track passes
    EXPLICIT_ONLY_SKILLS_CAP (75); the with-inferred track passes 100."""
    base = 0.0
    seen: set[str] = set()
    for raw in skills:
        s = raw.strip().lower()
        if s in seen:
            continue
        seen.add(s)
        if s in SKILL_TIERS_HIGH:
            base += 25
        elif s in SKILL_TIERS_MID:
            base += 15
        elif s in SKILL_TIERS_LOW:
            base += 5
        else:
            base += 8  # unknown skill — partial credit, don't ignore
    return float(min(cap, base))


def _inferred_bonus(inferred_capabilities: list) -> float:
    """Confidence-weighted bonus from inferred capabilities, capped at
    INFERRED_BONUS_CAP. Used as the non-tech-role fallback in
    `_skills_coverage_score`.

    must_have capabilities contribute the full multiplier; nice_to_have
    capabilities contribute half, so role-critical signal dominates
    soft / adjacent signal in the score.
    """
    raw = 0.0
    for cap in inferred_capabilities:
        weight = INFERRED_BONUS_PER_CAPABILITY * cap.confidence
        if cap.relevance == "nice_to_have":
            weight *= 0.5
        raw += weight
    return min(INFERRED_BONUS_CAP, raw)


def _role_progression_score(role: str, signal: str, years: int) -> float:
    """Junior→Mid→Senior signal, anchored on title keywords + years."""
    low = role.lower()
    if signal == "principal":
        return 95.0
    if signal == "senior" or any(kw in low for kw in SENIOR_TITLE_KEYWORDS):
        return 80.0 + (5.0 if years >= 10 else 0.0)
    if signal == "junior" or any(kw in low for kw in JUNIOR_TITLE_KEYWORDS):
        return 25.0
    if signal == "mid":
        return 55.0
    # unknown — infer from years alone
    if years >= 10:
        return 75.0
    if years >= 5:
        return 55.0
    if years >= 2:
        return 35.0
    return 20.0


def _education_score(
    highest: str,
    institution: str,
    field_of_study: str,
    analysis_role: str,
) -> float:
    """Education score = base degree value + prestige + field-relevance modifier.

    - Lowered base map (master = 50, not 85) so prestige + field bonus
      lands the typical case around 55-65, not 90.
    - Empty field_of_study → half credit (we know the degree level but
      can't judge relevance for the role).
    - Match (same family or role-family unknown / field-family unknown)
      → +5 only for direct match.
    - Adjacent (e.g. tech_adjacent + tech) → 0 modifier.
    - Mismatch (clearly wrong field for role) → -25 hard penalty,
      "irrelevant education shouldn't carry weight".
    - "none" → 0, never lifted by prestige / field bonus (safety floor
      stays at 60 only when institution looks academic but degree label
      missing — narrow safety net for sparse CVs).
    """
    if highest == "none":
        # No degree → 0. Per user direction: "kdo nema education uvedeny
        # tak 0 za education navic". No institution-only safety net.
        return 0.0

    base = EDUCATION_BASE_MAP.get(highest, 0.0)
    inst_low = (institution or "").lower()
    if any(kw in inst_low for kw in PRESTIGE_INSTITUTION_KEYWORDS):
        base += EDUCATION_PRESTIGE_BONUS

    if not (field_of_study or "").strip():
        # No field info — half credit. Known degree level alone is half signal.
        return max(0.0, min(100.0, base * EDUCATION_EMPTY_FIELD_MULTIPLIER))

    role_family = _classify_role_family(analysis_role)
    field_family = _classify_field_family(field_of_study)

    if role_family == "unknown" or field_family == "unknown":
        modifier = 0.0
    elif role_family == field_family:
        modifier = EDUCATION_FIELD_MATCH_BONUS
    elif (role_family, field_family) in ROLE_FIELD_ADJACENT_PAIRS:
        modifier = 0.0
    else:
        modifier = -EDUCATION_FIELD_MISMATCH_PENALTY

    return max(0.0, min(100.0, base + modifier))


def _classify_role_family(role: str) -> str:
    """Return the family bucket for a role title via substring keyword match."""
    low = (role or "").lower()
    for family, keywords in ROLE_FAMILY_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return family
    return "unknown"


def _classify_field_family(field: str) -> str:
    """Return the family bucket for a field-of-study via substring match."""
    low = (field or "").lower()
    if not low.strip():
        return "unknown"
    for family, keywords in FIELD_FAMILY_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return family
    return "unknown"
