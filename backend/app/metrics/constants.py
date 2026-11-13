"""Every tunable number for metrics lives here (spec §4.5).

Values marked "carried over" come from the first pipeline (removed Nov 4) so results stayed
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
# Reel views swing more than YouTube views (median spread 0.47-0.61 vs 0.44 on Nov 13 data), so
# Instagram's cut-offs are 1.3x wider; the same share of creators lands in each band on every platform.
RELIABILITY_SCALE_BY_PLATFORM = {"instagram": 1.3}
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
# Prior median engagement rate (likes+comments per view) by platform and tier: each creator is ranked
# against its own platform and size, so a score means the same on every platform (decided Nov 13).
# Set from the creators measured on production on Nov 13 (median per platform/tier: YouTube micro 1.98%
# n=28, mid 1.55% n=39; Instagram reels micro 1.99% n=17, mid 1.35% n=12; X micro/mid 1.64% n=8);
# tiers without enough data are extrapolated. Real peers replace these once a platform/tier has MIN_PEERS.
ENGAGEMENT_PRIOR: dict[str, dict[str, float]] = {
    "youtube": {"nano": 0.028, "micro": 0.020, "mid": 0.0155, "macro": 0.012, "mega": 0.009},
    "x": {"nano": 0.022, "micro": 0.0165, "mid": 0.0135, "macro": 0.010, "mega": 0.008},
    "instagram": {"nano": 0.028, "micro": 0.020, "mid": 0.0135, "macro": 0.010, "mega": 0.008},
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

# --- Post analysis for the creator panel (app/metrics/posts.py) -----------------------------------------
POSTS_IN_LEAD = 12  # posts sent to the UI per creator (tabs: best match, above usual, latest)
MATCH_MIN_TERM_SHARE = 0.6  # a topic matches a post if this share of its meaningful words appear in it
ABOVE_USUAL_FROM = 1.5  # "above their usual": reach at least 1.5x the creator's median
DESCRIPTION_SUMMARY_CHARS = 1000  # the opening paragraph (cut at the first blank line or link), at most this long
YOUNG_POST_DAYS = 7  # newer posts are still collecting views: shown as "new" and left out of the usual
# Phrases that mark a paid promotion in a title, caption or description (lower-case)
SPONSOR_PHRASES = ("sponsored by", "for sponsoring", "use code", "use my code", "promo code", "paid partnership",
                   "#ad", "#sponsored", "in partnership with", "brought to you by", "affiliate link")

# A creator who mostly posts photos is measured on their reels' views when at least this many have views.
MIN_POSTS_WITH_VIEWS = 3
