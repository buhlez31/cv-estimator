"""Role title → CZ-ISCO 4-digit code.

Deterministic keyword-based mapping. Trade-off: simpler than an LLM enum picker,
no API cost, fully testable. Misses for ambiguous titles fall back to a sane
default. This is a documented design choice — see README.
"""

# (priority, keywords-any-of, cz_isco_code)
# Higher priority first (longer / more specific phrases).
_RULES: list[tuple[int, tuple[str, ...], str]] = [
    (100, ("ict manager", "head of it", "cto", "vp engineering", "engineering director"), "1330"),
    (95, ("data scientist", "ml engineer", "machine learning engineer", "ai engineer"), "2519"),
    (90, ("data engineer",), "2519"),
    (90, ("database administrator", "dba", "data architect"), "2521"),
    (85, ("systems administrator", "sysadmin", "sre", "site reliability"), "2522"),
    (
        85,
        ("network engineer", "network administrator", "devops engineer", "platform engineer"),
        "2523",
    ),
    (80, ("systems analyst", "business analyst", "data analyst", "bi developer"), "2511"),
    (80, ("frontend", "front-end", "front end", "web developer"), "2513"),
    (75, ("mobile developer", "ios developer", "android developer"), "2514"),
    (
        70,
        (
            "backend",
            "back-end",
            "back end",
            "software engineer",
            "software developer",
            "developer",
            "programmer",
            "engineer",
        ),
        "2512",
    ),
    (40, ("technician", "support engineer", "helpdesk", "it support"), "3512"),
]
_DEFAULT_ISCO = "2519"


def map_to_cz_isco(role: str) -> str:
    """Return best-match CZ-ISCO 4-digit code for a role title."""
    if not role:
        return _DEFAULT_ISCO
    low = role.lower()
    best: tuple[int, str] | None = None
    for priority, keywords, code in _RULES:
        if any(kw in low for kw in keywords):
            if best is None or priority > best[0]:
                best = (priority, code)
    return best[1] if best else _DEFAULT_ISCO
