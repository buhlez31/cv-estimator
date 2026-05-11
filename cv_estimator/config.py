"""Constants for the cv_estimator pipeline.

Weights are FIXED per case study brief. Document in README, do not optimize.
"""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent
REPO_ROOT = PACKAGE_ROOT.parent
# Both directories live inside the installed package so they ship via
# package-data in any deploy target (e.g. Streamlit Cloud's `pip install .`).
DATA_DIR = PACKAGE_ROOT / "data"
PROMPTS_DIR = PACKAGE_ROOT / "prompts"
# Raw MPSV ingest artefacts stay outside the package (gitignored).
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"

# --- Scoring weights (sum must equal 1.0) ---
WEIGHT_YEARS = 0.30
WEIGHT_SKILLS = 0.35
WEIGHT_ROLE = 0.20
WEIGHT_EDUCATION = 0.15

# --- Years experience normalization ---
YEARS_CAP = 15  # 15+ years saturates at 100

# --- Skills coverage (LLM-driven for all roles) ---
# Inferred capability confidence threshold for inclusion in the LLM's
# input list (caps below this are deemed too speculative to feed the
# coverage scorer). Skepticism / overclaim handling lives in the prompt
# itself (`prompts/skills_coverage.md`); no Python-side penalty.
INFERRED_COVERAGE_CONFIDENCE_THRESHOLD = 0.6

# --- Role progression heuristics ---
SENIOR_TITLE_KEYWORDS = {
    "senior",
    "principal",
    "staff",
    "lead",
    "head",
    "director",
    "architect",
    "manager",
    "vp",
    "chief",
}
JUNIOR_TITLE_KEYWORDS = {"junior", "intern", "trainee", "graduate"}

# --- Education ---
HIGHER_ED_KEYWORDS = {
    "bachelor",
    "master",
    "msc",
    "bsc",
    "phd",
    "mba",
    "doctorate",
    "ing.",
    "mgr.",
    "bc.",
}
PRESTIGE_INSTITUTION_KEYWORDS = {
    "mit",
    "stanford",
    "harvard",
    "oxford",
    "cambridge",
    "eth",
    "cvut",
    "čvut",
    "vse",
    "vše",
    "muni",
    "uk praha",
    "charles university",
}

# --- Role-family classification (for education field-relevance modifier) ---
# Substring match on the analysis_role string. First matching family wins.
ROLE_FAMILY_KEYWORDS: dict[str, set[str]] = {
    "tech": {
        "engineer",
        "developer",
        "programmer",
        "scientist",
        "analyst",
        "architect",
        "sysadmin",
        "devops",
        "sre",
        "technician",
        "programátor",
        "vývojář",
        "technik",
        "ml ",
        "ai ",
        "ai/",
    },
    "business_mgmt": {
        "manager",
        "director",
        "head of",
        "vp",
        "chief",
        "ceo",
        "cfo",
        "coo",
        "cto",
        "cio",
        "principal",
    },
    "marketing_comms": {
        "marketing",
        "brand",
        "content",
        "growth",
        "communications",
        "pr ",
        "copywriter",
    },
    "sales_biz_dev": {
        "sales",
        "account ",
        "business development",
    },
    "design_creative": {
        "designer",
        "ux",
        "ui",
        "creative",
        "artist",
        "photographer",
    },
    "legal_compliance": {
        "lawyer",
        "legal",
        "compliance",
        "paralegal",
    },
    "ops_admin": {
        "operations",
        "administrator",
        "coordinator",
        "hr ",
        "recruiter",
    },
    "healthcare": {
        "doctor",
        "nurse",
        "pharmacist",
    },
}

# --- Field-of-study family classification ---
# Substring match on the field_of_study string. First matching family wins.
# IMPORTANT: tech_adjacent is checked BEFORE tech so "Geoinformatika" doesn't
# get swallowed by the "informatika" substring sitting under tech.
FIELD_FAMILY_KEYWORDS: dict[str, set[str]] = {
    "tech_adjacent": {
        "industrial engineering",
        "průmyslové inženýrství",
        "statistics",
        "statistika",
        "geoinformatics",
        "geoinformatika",
        "biotechnology",
        "biotechnologie",
        "robotics",
        "robotika",
        "applied mathematics",
        "aplikovaná matematika",
        "quantitative finance",
        "operations research",
    },
    "tech": {
        "computer science",
        "informatika",
        "software engineering",
        "softwarov",
        "electrical engineering",
        "elektrotechnika",
        "mathematics",
        "matematika",
        "physics",
        "fyzika",
        "data science",
        "machine learning",
        "artificial intelligence",
        "umělá inteligence",
        "cybersecurity",
        "kybernetická bezpečnost",
    },
    "business": {
        "mba",
        "business administration",
        "ekonomie",
        "economics",
        "finance",
        "accounting",
        "supply chain",
        "management",
    },
    "marketing": {
        "marketing",
        "communications",
        "journalism",
        "media studies",
        "advertising",
        "public relations",
    },
    "design_creative": {
        "graphic design",
        "fine arts",
        "architecture",
        "fashion design",
        "industrial design",
        "visual arts",
    },
    "legal": {
        "law",
        "legal studies",
        "právo",
        "právní",
    },
    "healthcare": {
        "medicine",
        "nursing",
        "pharmacy",
        "biology",
        "biomedical",
        "medicína",
    },
    "humanities": {
        "history",
        "philosophy",
        "literature",
        "languages",
        "art history",
        "sociology",
        "anthropology",
        "historie",
        "filozofie",
    },
}

# Pairs (role_family, field_family) treated as neutral (modifier = 0)
# instead of penalised. Asymmetric — both directions listed if both apply.
ROLE_FIELD_ADJACENT_PAIRS: set[tuple[str, str]] = {
    ("tech", "tech_adjacent"),
    ("tech_adjacent", "tech"),
    ("business_mgmt", "tech"),
    ("business_mgmt", "business"),
    ("ops_admin", "business"),
}

# Education degree base map. Lowered from the previous 0/15/60/85/95
# baseline so the typical master-with-prestige case is ~55, not ~90 —
# field-relevance modifiers swing the final score around this base
# instead of sitting on top of a saturated number.
EDUCATION_BASE_MAP: dict[str, float] = {
    "none": 0.0,
    "high_school": 10.0,
    "bachelor": 30.0,
    "master": 50.0,
    "phd": 70.0,
}
EDUCATION_PRESTIGE_BONUS = 5.0
EDUCATION_FIELD_MATCH_BONUS = 5.0
EDUCATION_FIELD_MISMATCH_PENALTY = 25.0
# When field_of_study is missing entirely (LLM couldn't find one), apply
# half credit to the base + prestige — degree level alone is half signal.
EDUCATION_EMPTY_FIELD_MULTIPLIER = 0.5

# --- CZ-ISCO IT-relevant code prefixes ---
IT_ISCO_PREFIXES = ("251", "252", "1330", "351")

# --- Score → ISPV percentile mapping ---
SCORE_TO_PERCENTILE = [
    # (max_score, percentile_label)
    (40, "P25"),
    (60, "P50"),
    (80, "P75"),
    (100, "P90"),
]

# --- Anthropic API ---
LLM_MODEL = "claude-sonnet-4-5"
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.0

# --- Salary sanity bounds (CZK monthly gross) ---
SALARY_FLOOR = 25_000
SALARY_CEILING = 500_000

# --- ISPV sample-size confidence buckets (in thousands of employees) ---
HIGH_SAMPLE_THRESHOLD = 5.0  # >= 5000 sampled employees → "high"
LOW_SAMPLE_THRESHOLD = 1.0  # < 1000 → "low" (P90 statistically noisy)

# --- Salary band width by ISPV confidence ---
SALARY_BAND_PCT_HIGH = 0.15  # ±15 % around interpolated median
SALARY_BAND_PCT_LOW = 0.25  # ±25 % widening when sample is thin

# --- Regional wage multipliers (Layer B) ---
REGIONAL_MULTIPLIERS_PATH = PACKAGE_ROOT / "data" / "regional_multipliers_2025.csv"

# --- Apify live job postings (Layer C) ---
APIFY_ACTOR_ID = "abaddion/jobscz-scraper"
APIFY_CACHE_TTL_HOURS = 24
APIFY_MAX_RESULTS = 50
# Weight given to the Apify live median when blending with the ISPV-anchored
# point estimate. ISPV is authoritative (national-scale official sample) so
# it keeps the dominant weight; live postings nudge the number toward
# present-day market.
APIFY_BLEND_WEIGHT = 0.30  # 30 % Apify, 70 % ISPV
