"""Role title → CZ-ISCO 4-digit code.

Hybrid mapping:
1. **Keyword rules** (deterministic, free) — handle ~30 common job titles
   across tech, management, professional, healthcare, legal, design,
   customer service. Word-boundary regex match.
2. **LLM fallback** — if no keyword rule fires, ask the model to pick
   the best CZ-ISCO code from the catalogue of 296 codes loaded from
   `data/ispv_2025.csv`. Caches per role string so repeated CVs with
   the same unusual title don't re-query.
3. **UnmappedRoleError** — raised only if BOTH rules and LLM fail
   (LLM returns "UNMATCHED" or an invalid code). Surfaces to UI as
   "role not found, please specify directly".

The LLM call only fires for edge cases (~10-20% of CVs in practice);
common roles cost $0 to map.
"""

import re
from functools import lru_cache
from pathlib import Path

from cv_estimator.config import DATA_DIR

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
    # --- Generic Czech / English catch-alls (lowest tier before LLM fallback) ---
    # Fire only when no specific keyword above matched; serves as a free
    # safety-net for the common Czech generic terms LLM #1 may emit.
    (45, ("analyst", "analytik"), "2511"),  # systems / business analyst NEC
    (45, ("manažer", "manazer"), "1219"),  # business services manager NEC
    (45, ("specialista",), "2422"),  # policy/admin specialist
    (45, ("konzultant", "consultant"), "2422"),  # business consultant
    (45, ("ředitel", "reditel"), "1120"),  # general director
    (45, ("vývojář", "vyvojar"), "2512"),  # generic developer (Czech)
    # --- IT support (lowest tech priority) ---
    (40, ("it support", "helpdesk", "support engineer"), "3512"),
    (40, ("technician",), "3512"),
    # --- Generic engineer catch-all (lowest, only fires for unspecific titles) ---
    (30, ("engineer",), "2512"),
]


class UnmappedRoleError(ValueError):
    """Raised when a role string matches no keyword rule.

    Per user direction: no silent fallback to a default CZ-ISCO. The
    caller (UI / CLI) must surface a clear "role not found in ISPV
    database — please specify a more common job title" message.
    """

    def __init__(self, role: str) -> None:
        self.role = role
        super().__init__(
            f"Role {role!r} did not match any CZ-ISCO keyword rule. "
            "Specify a more standard job title (e.g. 'Senior Backend "
            "Engineer', 'Marketing Manager', 'Lawyer') or leave the "
            "target-role field empty to use the auto-detected role from "
            "the CV."
        )


@lru_cache(maxsize=256)
def _kw_pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(keyword)}\b")


@lru_cache(maxsize=1)
def _valid_codes() -> frozenset[str]:
    """Load the set of valid CZ-ISCO codes from the ISPV CSV.

    Single-line read; avoids importing salary/lookup.py to keep this
    module free of cyclic dependencies.
    """
    csv_path: Path = DATA_DIR / "ispv_2025.csv"
    codes: set[str] = set()
    with csv_path.open(encoding="utf-8") as f:
        next(f, None)  # header
        for line in f:
            code = line.split(",", 1)[0].strip()
            if code:
                codes.add(code)
    return frozenset(codes)


def _try_keyword_rules(role: str) -> str | None:
    """Run the priority-ranked keyword rules. Return the matched code,
    or None if nothing fires."""
    low = role.lower()
    best: tuple[int, str] | None = None
    for priority, keywords, code in _RULES:
        if any(_kw_pattern(kw).search(low) for kw in keywords):
            if best is None or priority > best[0]:
                best = (priority, code)
    return best[1] if best is not None else None


@lru_cache(maxsize=256)
def _llm_fallback(role: str) -> str:
    """Call LLM to pick the best CZ-ISCO from the catalogue when no
    keyword rule matched. Cached per role string to avoid re-querying.

    Imported lazily to keep test fixtures that don't exercise the
    fallback path from needing to set up the Anthropic client.
    """
    from cv_estimator import llm  # local import (lazy, avoids test setup cost)

    valid = _valid_codes()
    codes_list = "\n".join(f"- {code}" for code in sorted(valid))
    prompt = llm.render_prompt("role_to_cz_isco", role=role, codes=codes_list)
    payload = llm.call_json(prompt)
    picked = (payload.get("code") or "").strip()
    if picked == "UNMATCHED" or picked not in valid:
        raise UnmappedRoleError(role)
    return picked


def map_to_cz_isco(role: str) -> str:
    """Return best-match CZ-ISCO 4-digit code for a role title.

    Two-stage resolution:
    1. Try the priority-ranked keyword rules (free, deterministic).
    2. If no rule matches, fall back to an LLM call that picks from the
       full 296-code CSV catalogue.

    Raises `UnmappedRoleError` only when both stages fail (LLM returns
    "UNMATCHED" or an invalid code). Callers must catch and surface the
    error to the user.
    """
    if not role:
        raise UnmappedRoleError(role)
    matched = _try_keyword_rules(role)
    if matched is not None:
        return matched
    return _llm_fallback(role)
