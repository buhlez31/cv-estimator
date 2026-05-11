"""Role title → CZ-ISCO 4-digit code.

Deterministic keyword-based mapping. Trade-off: simpler than an LLM enum picker,
no API cost, fully testable. Misses for ambiguous titles fall back to a sane
default. This is a documented design choice — see README.

Coverage extended in Phase 6 to non-IT roles (healthcare, education, legal,
marketing, sales, finance, design) so the salary lookup can use the full
296-row ISPV CSV instead of just the 14 IT codes.

Matching uses regex word boundaries (`\\bKEYWORD\\b`) so short abbreviations
like "cto", "ceo", "cio" don't accidentally match inside longer words
("director" contains the substring "cto", "doctor" contains "cto", etc.).
"""

import re
from functools import lru_cache

# (priority, keywords-any-of, cz_isco_code)
# Higher priority wins on conflict. Rules grouped by domain for readability.
_RULES: list[tuple[int, tuple[str, ...], str]] = [
    # --- C-suite / top management ---
    (
        100,
        ("ict manager", "head of it", "cto", "cio", "vp engineering", "engineering director"),
        "1330",
    ),
    (100, ("ceo", "chief executive", "managing director", "general manager"), "1120"),
    (100, ("cfo", "chief financial officer", "finance director", "head of finance"), "1211"),
    (100, ("hr director", "head of hr", "people director", "chro", "chief people officer"), "1212"),
    (100, ("cmo", "marketing director", "head of marketing"), "1221"),
    (100, ("cso", "sales director", "head of sales", "vp sales"), "1221"),
    # --- Tech professionals (25xx) ---
    (95, ("data scientist", "ml engineer", "machine learning engineer", "ai engineer"), "2519"),
    (90, ("data engineer",), "2519"),
    (90, ("database administrator", "dba", "data architect"), "2521"),
    (85, ("systems administrator", "sysadmin", "sre", "site reliability"), "2522"),
    (
        85,
        ("network engineer", "network administrator", "devops engineer", "platform engineer"),
        "2523",
    ),
    (80, ("systems analyst", "data analyst", "bi developer"), "2511"),
    (80, ("frontend", "front-end", "front end", "web developer"), "2513"),
    (75, ("mobile developer", "ios developer", "android developer"), "2514"),
    # --- Healthcare / education / design professionals ---
    (75, ("doctor", "physician", "lékař"), "2211"),
    (75, ("teacher", "professor", "lecturer", "učitel"), "2330"),
    (75, ("ux designer", "ui designer", "product designer", "graphic designer"), "2166"),
    # --- Mid-level managers (1xxx, ranked below C-suite) ---
    (75, ("marketing manager", "brand manager", "growth manager"), "1221"),
    (75, ("sales manager", "account manager", "key account"), "1221"),
    (75, ("finance manager", "controller"), "1211"),
    (75, ("hr manager", "people manager", "talent manager"), "1212"),
    # --- Tech SW dev catch-all (lower priority than specialised tech roles) ---
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
        ),
        "2512",
    ),
    # --- Professional individual contributors (24xx, 26xx) ---
    (70, ("business analyst",), "2511"),
    (70, ("financial analyst", "auditor"), "2411"),
    (70, ("accountant", "účetní"), "2411"),
    (
        70,
        (
            "hr business partner",
            "talent acquisition",
            "recruiter",
            "people partner",
            "hr specialist",
        ),
        "2423",
    ),
    (
        70,
        ("marketing specialist", "seo specialist", "performance marketer", "digital marketing"),
        "2431",
    ),
    (70, ("sales specialist", "business development"), "2433"),
    (70, ("lawyer", "attorney", "právník", "legal counsel"), "2611"),
    (70, ("compliance officer", "compliance specialist"), "2611"),
    # --- Healthcare associates ---
    (70, ("nurse", "registered nurse", "sestra"), "2221"),
    (70, ("pharmacist", "lékárník"), "2262"),
    # --- Associate-level / support roles ---
    (60, ("paralegal", "legal assistant"), "3411"),
    (50, ("customer success", "customer service", "customer care"), "4222"),
    # --- IT support (lowest tech priority) ---
    (40, ("it support", "helpdesk", "support engineer"), "3512"),
    (40, ("technician",), "3512"),
    # --- Generic engineer catch-all (lowest, only fires for unspecific titles) ---
    (30, ("engineer",), "2512"),
]
_DEFAULT_ISCO = "2519"


@lru_cache(maxsize=256)
def _kw_pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(keyword)}\b")


def map_to_cz_isco(role: str) -> str:
    """Return best-match CZ-ISCO 4-digit code for a role title."""
    if not role:
        return _DEFAULT_ISCO
    low = role.lower()
    best: tuple[int, str] | None = None
    for priority, keywords, code in _RULES:
        if any(_kw_pattern(kw).search(low) for kw in keywords):
            if best is None or priority > best[0]:
                best = (priority, code)
    return best[1] if best else _DEFAULT_ISCO
