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
# ...but only where the platform normally lists a country, so a missing one is a warning sign. Instagram and
# X never show it: there the creator keeps the "country unknown" badge and isn't marked down (decided Nov 13).
COUNTRY_LISTED_PLATFORMS = {"youtube", "linkedin"}
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

# --- the negotiation agent (app/negotiation/, spec §8.7) ---
NEGOTIATION_QUESTIONS_VERSION = "negotiation-v2"  # replaces reply-v1..v3 (the code-formula helper)
NEGOTIATION_SIGNAL_FROM = 0.6  # a yes/no about their reply (declined, agrees…) counts from this probability
NEGOTIATION_INJECTION_ABOVE = 0.5  # the reply is ignored if it looks aimed at an AI
DRAFT_EXTRA_PROMISE_ABOVE = 0.5  # a draft that promises undecided things is rewritten
MOVES = {
    "accept": "Agree to what they asked: it's fair for us",
    "counter": "Offer different terms closer to our budget",
    "restructure": "Change the kind of deal (for example less fee, more commission, or a smaller scope)",
    "hold": "Repeat our last offer: they're asking too much and we've already moved",
    "walk_away": "Politely end it: they're far above what the deal is worth and won't move",
}
STRUCTURES = {
    "flat": "A fixed fee only",
    "fee_plus_commission": "A smaller fixed fee plus commission on sales or signups from their link",
    "commission_only": "Commission only, no fixed fee",
    "smaller_scope": "Their price, but a smaller deliverable (no paid-ads use or exclusivity)",
}
COMMISSION_STEPS = ("0", "5", "10", "15", "20", "25")  # % on sales; Jev picks one
CONCESSION_LEVELS = (  # Jev's Score: how far to move from our last offer toward their ask
    "Hold firm: don't move",
    "Move a little",
    "Move a fair amount",
    "Meet in the middle",
    "Move most of the way",
)
EXTRAS = {
    "none": "Nothing extra",
    "repeat_posts": "Offer a follow-up post or a longer partnership if this one works",
    "free_product": "Offer free access to the product",
    "fast_payment": "Offer to pay quickly, as soon as the post is live",
}

# Track: what the audience said under a sponsored video (spec §7.6)
COMMENT_SENTIMENT_LEVELS = ("Very negative", "Mostly negative", "Mixed", "Mostly positive", "Very positive")
COMMENT_SIGNAL_FROM = 0.6
