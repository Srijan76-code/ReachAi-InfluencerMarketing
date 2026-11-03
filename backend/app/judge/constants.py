"""Every Jev threshold and scoring weight (spec §4.6–4.7). These are what humans review and tune.

Bump QUESTIONS_VERSION whenever a question's wording changes: saved Jev answers are keyed by it,
so changed questions are never mixed with old answers.
"""

QUESTIONS_VERSION = "creator-v1"

# How much creator text goes into one Jev request (keeps requests small and cheap).
MAX_POSTS_IN_STATE = 12
MAX_POST_CHARS = 280
MAX_BIO_CHARS = 600

# Number of levels in each Score question (must match questions.py; a test checks this).
SCORE_LEVELS = {"topic_fit": 5, "audience_stage": 4, "safety_risk": 4}

# --- Fit (spec §4.7) -------------------------------------------------------------------
FIT_WEIGHTS = {"topic_fit": 0.5, "audience_stage": 0.3, "pain_point": 0.2}

# --- Final score -----------------------------------------------------------------------
FINAL_WEIGHTS = {"fit": 0.55, "health": 0.30}
RISK_WEIGHT = 0.40
RISING_BONUS = 0.10
TREND_BONUS = 0.05
TREND_THRESHOLD = 0.6
PROMO_RISK_FACTOR = 0.5  # "mostly ads" counts half as much as a safety problem
ANOMALY_RISK_FROM = 0.6  # anomaly scores below this add no risk

# --- Hard drops (spec §4.7). Each is (question id, comparison, threshold) ---------------------
DROP_NOT_INDIVIDUAL_BELOW = 0.4
DROP_LANGUAGE_BELOW = 0.3
DROP_KIDS_ABOVE = 0.6  # only when the brief excludes kids content
DROP_INJECTION_ABOVE = 0.5

# --- Labels ----------------------------------------------------------------------------
STRONG_BUY_FROM = 75
CONSIDER_FROM = 55

# --- Platform choice (spec §4.9) ---------------------------------------------------------------
PLATFORM_ADD_ABOVE = 0.7
PLATFORM_LOW_FIT_BELOW = 0.3
PRESET_PLATFORMS = {"b2b": ["youtube", "x", "linkedin"], "consumer": ["youtube", "instagram"]}

NICHES = [
    "ai_and_ml", "software_development", "data_science", "tech_reviews", "startups_and_business",
    "marketing_and_growth", "personal_finance", "investing_and_crypto", "careers_and_jobs", "education_and_exams",
    "productivity", "design", "health_and_fitness", "food_and_cooking", "beauty_and_fashion", "travel",
    "gaming", "entertainment_and_comedy", "music", "parenting_and_family", "lifestyle_vlog", "news_and_politics",
    "science", "sports", "automotive",
]

AUDIENCE_ROLES = [
    "founders", "developers", "marketers", "sales", "designers", "students", "job_seekers", "general_consumers",
]
