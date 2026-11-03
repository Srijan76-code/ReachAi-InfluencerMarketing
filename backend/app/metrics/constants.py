"""Every tunable number for metrics lives here (spec §4.5).

Values marked "carried over" come from the current pipeline (app/my_agent) so results stay
comparable. Values marked "prior" are starting points until our creator database has enough
peers (MIN_PEERS) to compute them from real data.
"""

# --- Follower tiers -----------------------------------------------------------
# (upper bound exclusive, name)
FOLLOWER_TIERS: list[tuple[float, str]] = [
    (10_000, "nano"),
    (100_000, "micro"),
    (500_000, "mid"),
    (1_000_000, "macro"),
    (float("inf"), "mega"),
]

# --- Posts ----------------------------------------------------------------------
NEWEST_N = 5  # "recent" window for momentum and outperformance
COMPARE_UP_TO = 15  # older window = posts NEWEST_N+1 .. COMPARE_UP_TO
MIN_POSTS_FOR_MOMENTUM = 8  # need at least 5 new + 3 older posts with views

# --- Reliability (MAD / median of views) -----------------------------------------
RELIABILITY_HIGH_BELOW = 0.35
RELIABILITY_MEDIUM_BELOW = 0.8
RELIABILITY_SCORE = {"High": 1.0, "Medium": 0.6, "Low": 0.3}

# --- Activity ---------------------------------------------------------------------
DEAD_AFTER_DAYS = 180  # carried over
CADENCE_SCORE_STEPS: list[tuple[int, float]] = [(14, 1.0), (45, 0.7), (90, 0.4)]  # days since last post -> score
CADENCE_SCORE_FLOOR = 0.1

# --- Rising creators ---------------------------------------------------------------
RISING_MOMENTUM = 1.5
RISING_MAX_DAYS_SINCE_POST = 14
RISING_OUTPERFORMANCE = 1.0

# --- Engagement percentile ------------------------------------------------------------
MIN_PEERS = 200  # below this, use the priors instead of real peers
# prior median engagement rate (likes+comments per view) by platform and tier
ENGAGEMENT_PRIOR: dict[str, dict[str, float]] = {
    "youtube": {"nano": 0.06, "micro": 0.045, "mid": 0.035, "macro": 0.03, "mega": 0.025},
    "x": {"nano": 0.02, "micro": 0.012, "mid": 0.008, "macro": 0.006, "mega": 0.005},
    "instagram": {"nano": 0.05, "micro": 0.03, "mid": 0.02, "macro": 0.015, "mega": 0.012},
    # LinkedIn has no public views; engagement is per follower
    "linkedin": {"nano": 0.03, "micro": 0.015, "mid": 0.008, "macro": 0.005, "mega": 0.004},
}
# engagement 3x the prior median -> percentile 1.0; one third of it -> 0.0
ENGAGEMENT_PRIOR_SPREAD = 3.0

# --- Health ---------------------------------------------------------------------------
HEALTH_WEIGHTS = {"engagement": 0.4, "reliability": 0.3, "cadence": 0.3}

# --- Gates (hard filters before any paid judging) ----------------------------------------
MIN_MEDIAN_VIEWS = 200  # carried over (MIN_ABSOLUTE_VIEWS)
VIEW_FLOOR_BY_INDUSTRY = {  # carried over (INDUSTRY_VIEW_FLOORS)
    "fintech": 1000, "saas": 1000, "edtech": 2000, "d2c": 5000, "agency": 500, "other": 2000,
}
VIEW_FLOOR_PRICE_FACTOR = {"high": 0.5, "low": 2.0}  # carried over: high ticket halves, low ticket doubles

# --- Fake engagement (anomaly) ---------------------------------------------------------------
ANOMALY_EXCLUDE_ABOVE = 0.8
ANOMALY_WARN_ABOVE = 0.6
ANOMALY_MIN_TRAINING_ROWS = 500  # per platform, before the IsolationForest replaces the rules
ANOMALY_CONTAMINATION = 0.05
# rule-based fallback
ZOMBIE_ENGAGEMENT_BELOW = 0.005  # carried over (ZOMBIE_ENGAGEMENT_THRESHOLD)
LOW_COMMENT_RATIO_BELOW = 0.002  # comments per like; near-zero suggests bought likes
LOW_REACH_RATIO_BELOW = 0.005  # median views per follower, for accounts with 10k+ followers
LOW_REACH_MIN_FOLLOWERS = 10_000

# --- Price and clicks -----------------------------------------------------------------------
INDUSTRY_CPM = {  # carried over (USD per 1,000 views, tier-1 countries)
    "fintech": 35.0, "saas": 28.0, "edtech": 22.0, "tech": 15.0, "health": 12.0, "gaming": 6.0, "other": 8.0,
}
GEO_TIERS = {  # carried over
    1.0: {"US", "UK", "GB", "AU", "CA", "DE"},
    0.6: {"AE", "SG", "FR", "ES", "IT"},
    0.25: {"IN", "BR", "PH", "ID"},
}
GEO_DEFAULT = 0.5
PLATFORM_CPM_FACTOR = {"youtube": 1.0, "instagram": 0.8, "x": 0.6, "linkedin": 1.0}  # X runs 20–40% below Instagram
CTR_BY_INDUSTRY = {"tech": 0.025, "fintech": 0.03, "vlog": 0.008, "gaming": 0.01, "other": 0.015}  # carried over
# LinkedIn has no public views: typical transacted price per post by follower tier (Favikon/Naano priors)
LINKEDIN_PRICE_BY_TIER = {"nano": 150.0, "micro": 500.0, "mid": 1200.0, "macro": 2500.0, "mega": 5000.0}
# fair range around the point estimate, widened by unreliability
FAIR_RANGE = {"High": (0.85, 1.2), "Medium": (0.75, 1.3), "Low": (0.6, 1.5)}
