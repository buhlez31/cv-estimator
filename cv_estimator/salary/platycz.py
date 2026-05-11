"""Layer C — platy.cz role-title refinement.

ISPV gives the structural quantile curve per CZ-ISCO occupational class
(296 codes). platy.cz adds 513 specific role-title rows (e.g. "Backend
developer", "Solution architekt", "Advokát") with P10/P90 each. The
matcher finds the best platy.cz row for the candidate's analysis role
and exposes it to lookup.py for blending.
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from cv_estimator.config import DATA_DIR

PLATYCZ_CSV: Path = DATA_DIR / "platycz_2025.csv"


class PlatyczRow(BaseModel):
    category_slug: str
    position_slug: str
    position_label: str
    p10: int
    p90: int
    median_proxy: int
    url: str


# Cross-language aliases. Maps an English token to a set of equivalent
# Czech / English forms. Used to bridge "developer" (English CV) with
# "vyvojar" / "programator" (Czech platy.cz slug).
_ALIASES: dict[str, set[str]] = {
    "developer": {"developer", "vyvojar", "programator", "programmer"},
    "programmer": {"programator", "vyvojar", "developer", "programmer"},
    "engineer": {"engineer", "inzenyr"},
    "architect": {"architect", "architekt"},
    "manager": {"manager", "manazer"},
    "consultant": {"consultant", "konzultant"},
    "specialist": {"specialist", "specialista"},
    "analyst": {"analyst", "analytik"},
    "administrator": {"administrator", "spravce"},
    "designer": {"designer", "designér"},
    "tester": {"tester"},
    "lawyer": {"lawyer", "advokat", "pravnik"},
    "doctor": {"doctor", "lekar"},
    "nurse": {"nurse", "zdravotni-sestra", "sestra"},
    "accountant": {"accountant", "ucetni"},
    "salesman": {"salesman", "obchodnik", "zastupce"},
    "sales": {"sales", "obchodni", "zastupce", "obchodnik"},
    "representative": {"representative", "zastupce"},
    "teacher": {"teacher", "ucitel"},
    # Exec abbreviations → Czech director / leader equivalents. Multi-token
    # alias sets (e.g. `reditel` AND `it` for CTO) stack hit weights so the
    # row that covers both wins over a row that covers just one.
    "cto": {"cto", "cio", "it", "ict", "reditel"},
    "ceo": {"ceo", "generalni", "vykonny", "reditel"},
    "cfo": {"cfo", "financni", "ekonomicky", "reditel"},
    "coo": {"coo", "provozni", "reditel"},
    "director": {"director", "reditel"},
    "head": {"head", "vedouci"},
    "it": {"it", "ict"},
}

# Tokens that count as direct hits (1.0) vs alias hits (0.7) so a
# cross-language alias match doesn't outweigh a literal token match.
_ALIAS_HIT_WEIGHT = 0.7

# Tokens that don't, on their own, identify a role — used to forbid a
# match when the input contributes nothing more specific than these.
_GENERIC_TOKENS: set[str] = {
    "senior",
    "junior",
    "lead",
    "head",
    "principal",
    "staff",
    "intern",
    "trainee",
    "graduate",
    "the",
    "of",
    "and",
    "an",
    "a",
}

# Minimum token-overlap ratio (against input tokens) for a candidate row
# to be accepted as a match.
_MATCH_THRESHOLD = 0.5


@lru_cache(maxsize=1)
def _load() -> pd.DataFrame:
    if not PLATYCZ_CSV.exists():
        raise FileNotFoundError(
            f"platy.cz CSV missing at {PLATYCZ_CSV}. "
            "Run scripts/prepare_platycz_data.py or commit data/platycz_2025.csv."
        )
    df = pd.read_csv(PLATYCZ_CSV, dtype={"category_slug": str, "position_slug": str})
    return df


def _strip_diacritics(s: str) -> str:
    """Czech → ASCII so 'Vývojář' tokenises against the slug 'vyvojar'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_TOKEN_RE = re.compile(r"[^\w]+")


def _tokenise(s: str) -> set[str]:
    """Lowercase, strip diacritics, split on non-word chars."""
    clean = _strip_diacritics(s.lower())
    tokens = {t for t in _TOKEN_RE.split(clean) if t}
    return tokens


def _specific_tokens(tokens: set[str]) -> set[str]:
    return tokens - _GENERIC_TOKENS


def _row_tokens(row: pd.Series) -> set[str]:
    return _tokenise(f"{row['position_label']} {row['position_slug']}")


def _token_hit_weight(token: str, row_tokens: set[str]) -> float:
    """Direct hit = 1.0; alias hits stack at `_ALIAS_HIT_WEIGHT` each
    (capped at 1.0) so a row whose tokens cover MULTIPLE aliases of one
    input token outranks a row that only covers one. Miss = 0."""
    if token in row_tokens:
        return 1.0
    if token in _ALIASES:
        alias_hits = len(_ALIASES[token] & row_tokens)
        if alias_hits:
            return min(1.0, alias_hits * _ALIAS_HIT_WEIGHT)
    return 0.0


@lru_cache(maxsize=256)
def find_match(role: str) -> PlatyczRow | None:
    """Return the best-matching platy.cz row for `role`, or None when no
    row's token-overlap with the input clears the threshold.

    Tiebreaker: prefer rows with the highest weighted score, then more
    matched tokens, then smaller row_token set (tighter fit — penalises
    rows with lots of extra words).
    """
    if not role or not role.strip():
        return None

    raw_tokens = _tokenise(role)
    specific_input = _specific_tokens(raw_tokens)
    if not specific_input:
        return None

    df = _load()
    best_score = 0.0
    best_hits = 0
    best_row_size = 10**6
    best_idx: int | None = None

    for idx, row in df.iterrows():
        row_tokens = _row_tokens(row)
        weights = [_token_hit_weight(t, row_tokens) for t in specific_input]
        total = sum(weights)
        if total <= 0:
            continue
        hits = sum(1 for w in weights if w > 0)
        # Recall against specific input — generic words like "senior"
        # are excluded from the denominator so they neither inflate nor
        # depress the ratio.
        score = total / len(specific_input)
        # Strictly better → take. Tie → prefer more hits, then tighter row.
        better = (
            score > best_score
            or (score == best_score and hits > best_hits)
            or (score == best_score and hits == best_hits and len(row_tokens) < best_row_size)
        )
        if better:
            best_score = score
            best_hits = hits
            best_row_size = len(row_tokens)
            best_idx = idx

    if best_idx is None or best_score < _MATCH_THRESHOLD:
        return None

    row = df.iloc[best_idx]
    return PlatyczRow(
        category_slug=str(row["category_slug"]),
        position_slug=str(row["position_slug"]),
        position_label=str(row["position_label"]),
        p10=int(row["p10"]),
        p90=int(row["p90"]),
        median_proxy=int(row["median_proxy"]),
        url=str(row["url"]),
    )
