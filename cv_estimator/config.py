"""Constants for the cv_estimator pipeline.

Weights are FIXED per case study brief. Document in README, do not optimize.
"""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent
REPO_ROOT = PACKAGE_ROOT.parent
DATA_DIR = REPO_ROOT / "data"
PROMPTS_DIR = PACKAGE_ROOT / "prompts"

# --- Scoring weights (sum must equal 1.0) ---
WEIGHT_YEARS = 0.30
WEIGHT_SKILLS = 0.35
WEIGHT_ROLE = 0.20
WEIGHT_EDUCATION = 0.15

# --- Years experience normalization ---
YEARS_CAP = 15  # 15+ years saturates at 100

# --- Skills tier weights (used by scoring/components.py) ---
SKILL_TIER_HIGH = 1.0  # senior-signal tech (k8s, system design, ML infra, ...)
SKILL_TIER_MID = 0.6  # mainstream production tools (Docker, AWS, Kafka, ...)
SKILL_TIER_LOW = 0.3  # generic / commodity (Excel, basic Office, ...)

# --- Two-track skills_depth ceilings (see scoring/components.py) ---
# Buzzword-only baseline cannot reach 100 — a bare skill list without
# project-narrative evidence is inherently incomplete signal.
EXPLICIT_ONLY_SKILLS_CAP = 75.0
# Inferred capabilities are confidence-weighted and capped on their
# aggregate contribution. Tuned so a typical 3-capability senior CV
# lifts ~17 points of skills_depth (= ~6 points of seniority_score).
INFERRED_BONUS_PER_CAPABILITY = 8.0
INFERRED_BONUS_CAP = 25.0

# Heuristic skill→tier lookup (lower-case match). Extend as needed.
SKILL_TIERS_HIGH = {
    "kubernetes",
    "k8s",
    "system design",
    "distributed systems",
    "machine learning infrastructure",
    "mlops",
    "site reliability",
    "platform engineering",
    "kafka streams",
    "rust",
    "go",
    "terraform",
    "spark",
    "airflow",
    "kubeflow",
}
SKILL_TIERS_MID = {
    "python",
    "sql",
    "docker",
    "aws",
    "azure",
    "gcp",
    "postgres",
    "postgresql",
    "react",
    "typescript",
    "node",
    "node.js",
    "kafka",
    "redis",
    "elasticsearch",
    "snowflake",
    "bigquery",
    "fastapi",
    "django",
    "flask",
    "git",
    "ci/cd",
    "pandas",
    "numpy",
    "pytorch",
    "tensorflow",
}
SKILL_TIERS_LOW = {
    "excel",
    "powerpoint",
    "word",
    "office",
    "jira",
    "confluence",
    "slack",
    "outlook",
}

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
