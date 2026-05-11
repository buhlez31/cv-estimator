"""Layer C: live job-posting signal pulled from jobs.cz via the Apify
`abaddion/jobscz-scraper` actor.

Off by default — only fires when `APIFY_TOKEN` is set. ISPV stays the
authoritative source for the seniority-anchored point estimate; this is a
recency cross-check ("does the official 2025 band still hold up against
postings published last month?").

Cached for 24 h to keep per-analysis cost near zero. Cache key =
hash(role, region, max_results).
"""

import hashlib
import json
import os
import re
import statistics
from datetime import UTC, datetime
from pathlib import Path

from cv_estimator.config import (
    APIFY_ACTOR_ID,
    APIFY_CACHE_TTL_HOURS,
    APIFY_MAX_RESULTS,
)
from cv_estimator.models import MarketPostings

CACHE_DIR = Path.home() / ".cache" / "cv-estimator"


def _cache_key(role: str, region: str | None, max_results: int) -> str:
    raw = f"{role.lower().strip()}|{region or ''}|{max_results}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"apify_{key}.json"


def _read_cache(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fetched_at = datetime.fromisoformat(payload["fetched_at"])
    age_h = (datetime.now(UTC) - fetched_at).total_seconds() / 3600
    if age_h > APIFY_CACHE_TTL_HOURS:
        return None
    return payload


def _write_cache(key: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps(payload, default=str), encoding="utf-8")


# --- Salary string parsing ------------------------------------------------

_NUMBER_RE = re.compile(r"\d[\d\s ]*")


def _digits(s: str) -> int | None:
    """Extract leading number group from a string like '60 000 Kč'."""
    m = _NUMBER_RE.search(s)
    if not m:
        return None
    raw = re.sub(r"\D", "", m.group(0))
    if not raw:
        return None
    return int(raw)


def parse_salary(text: str | None) -> int | None:
    """Parse a posting salary string into monthly CZK (best-effort).

    Examples handled:
      "60 000 – 80 000 Kč"     → 70000 (midpoint)
      "60 000 - 80 000 Kč/měs" → 70000
      "od 70 000 Kč"           → 70000 (use as floor estimate)
      "70 000 Kč"              → 70000
      "1 200 Kč/hod"           → 1200 × 160 = 192000 (assumed hours/month)

    Returns None when the string has no parseable number or value is out
    of sane monthly range.
    """
    if not text:
        return None
    text = text.replace(" ", " ").lower()

    # Hourly → monthly (assume 160 working hours/month)
    is_hourly = "/hod" in text or "kč/h" in text or "hod." in text

    # Detect range via en/em dash or hyphen between two numbers
    range_match = re.search(r"(\d[\d\s]*)\s*[\-–—]\s*(\d[\d\s]*)", text)
    if range_match:
        low = _digits(range_match.group(1))
        high = _digits(range_match.group(2))
        if low and high:
            value = (low + high) // 2
        else:
            value = low or high
    else:
        value = _digits(text)

    if value is None:
        return None
    if is_hourly:
        value *= 160

    # Sanity: monthly CZK should be 10k–1M
    if value < 10_000 or value > 1_000_000:
        return None
    return value


# --- Apify client ---------------------------------------------------------


def _run_actor(role: str, region: str | None, max_results: int) -> list[dict]:
    """Synchronous Apify actor run. Returns the dataset items.

    Imports `apify_client` lazily so the rest of the pipeline keeps
    working when the dependency is absent (e.g. dev machines that
    haven't reinstalled requirements.txt)."""
    try:
        from apify_client import ApifyClient
    except ImportError:
        return []

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        return []

    client = ApifyClient(token)
    run_input = {
        "searchQueries": [role],
        "maxResults": max_results,
        "country": "cz",
    }
    if region:
        run_input["locality"] = region

    try:
        run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input, timeout_secs=120)
    except Exception:
        return []
    if not run or "defaultDatasetId" not in run:
        return []
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def fetch_market_postings(
    role: str,
    region: str | None = None,
    *,
    max_results: int = APIFY_MAX_RESULTS,
) -> MarketPostings | None:
    """Returns a MarketPostings summary or None if Apify is unconfigured
    / errored / returns no usable salary strings."""
    if not os.environ.get("APIFY_TOKEN"):
        return None

    key = _cache_key(role, region, max_results)
    cached = _read_cache(key)
    if cached is not None:
        return MarketPostings(**cached["payload"]) if cached.get("payload") else None

    items = _run_actor(role, region, max_results)
    salaries: list[int] = []
    for item in items:
        raw = item.get("salary") or item.get("salaryRange") or item.get("offeredSalary")
        parsed = parse_salary(raw)
        if parsed is not None:
            salaries.append(parsed)

    if not items:
        _write_cache(key, {"fetched_at": datetime.now(UTC).isoformat(), "payload": None})
        return None

    if not salaries:
        result = MarketPostings(
            sample_size=0,
            total_postings=len(items),
            median=None,
            p25=None,
            p75=None,
            fetched_at=datetime.now(UTC),
            sample_url=_sample_url(role, region),
        )
    else:
        salaries.sort()
        result = MarketPostings(
            sample_size=len(salaries),
            total_postings=len(items),
            median=int(statistics.median(salaries)),
            p25=int(_quantile(salaries, 0.25)),
            p75=int(_quantile(salaries, 0.75)),
            fetched_at=datetime.now(UTC),
            sample_url=_sample_url(role, region),
        )

    _write_cache(
        key,
        {
            "fetched_at": result.fetched_at.isoformat(),
            "payload": json.loads(result.model_dump_json()),
        },
    )
    return result


def _quantile(sorted_values: list[int], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _sample_url(role: str, region: str | None) -> str:
    """Build a jobs.cz search URL the reader can click through to."""
    from urllib.parse import urlencode

    params: dict[str, str] = {"q[]": role}
    if region:
        params["locality[code]"] = region
    return f"https://www.jobs.cz/prace/?{urlencode(params, doseq=True)}"
