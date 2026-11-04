"""Every Jev threshold and scoring weight (spec §4.6–4.7). These are what humans review and tune.

Bump QUESTIONS_VERSION whenever a question's wording changes: saved Jev answers are keyed by it,
so changed questions are never mixed with old answers.
"""

QUESTIONS_VERSION = "creator-v2"  # v2: audience-country question for creators with no listed country

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
COUNTRY_UNKNOWN_FACTOR = 0.8  # brief sets target countries, no country listed and Jev can't tell: score x 0.8, flagged
# Country by Jev (decided Nov 4: Jev only, no estimating in code). Asked only when the platform lists no country.
COUNTRY_JEV_ACCEPT_FROM = 0.6  # Jev names a target country with at least this confidence: treated as that country
COUNTRY_JEV_DROP_FROM = 0.75  # Jev says "another country" with at least this confidence: dropped like a wrong country
MAX_SUMMARIES_IN_STATE = 5  # post descriptions' opening lines sent with the country question
MAX_SUMMARY_CHARS = 200
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
# Calibrated Nov 4 on 63 scored creators and 19 blind ratings (1-5): at 60/45, 13% of scored creators are
# Strong Buy, no creator rated 1-2 is Strong Buy, and 4 of 10 rated 4-5 are. 75/55 gave no Strong Buy at
# all (the best real creator scored 67). Starting values: re-tune with more labels (roadmap K6).
STRONG_BUY_FROM = 60
CONSIDER_FROM = 45

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

# --- A creator's reply to a deal offer (app/deals/reply.py) ----------------------------------------
REPLY_QUESTIONS_VERSION = "reply-v1"
REPLY_SIGNAL_FROM = 0.6  # a reply signal (open to negotiate, wants commission…) counts from this probability
REPLY_INJECTION_ABOVE = 0.5  # the reply is ignored if it looks aimed at an AI
