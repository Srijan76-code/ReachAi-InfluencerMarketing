"""Track (spec §7.6, roadmap F7.11). Numbers here are starting values; tune them with real campaigns."""

# Share of a YouTube video's first-30-day views reached by day N after it goes live (typical curve:
# most views come in the first week). Used for the forecast; between points we interpolate.
VIEW_CURVE = ((0, 0.0), (1, 0.30), (2, 0.45), (3, 0.55), (7, 0.75), (14, 0.88), (30, 1.0))
FORECAST_DAYS = 30
FORECAST_MIN_DAYS = 2  # a post needs this many days of data before it's forecast

# Rebook / OK / Skip (code, not a model): against what we expected (their usual views × posts) and the
# campaign's average cost per result
TOO_EARLY_DAYS = 3
REBOOK_VIEWS_RATIO = 1.2
SKIP_VIEWS_RATIO = 0.5
REBOOK_COST_RATIO = 0.8
SKIP_COST_RATIO = 1.5

# Finding posts: each creator's newest uploads after the deal was agreed
UPLOADS_TO_CHECK = 10
JEV_MATCH_FROM = 0.7  # Jev's probability that an upload is the sponsored post
COMMENT_SUMMARY_AFTER_DAYS = 3
COMMENTS_TO_READ = 60
REFRESH_EVERY_MINUTES = 30  # "Check now" and opening Track: at most this often per campaign
TRACK_CRON = "17 6 * * *"  # daily, early UTC

GOAL_KINDS = ("signups", "sales", "views", "clicks")
PAY_METHODS = ("paypal", "bank", "upi", "wise", "other")
CONVERSION_KINDS = ("signup", "sale", "code_use")
GOAL_TO_CONVERSION = {"signups": "signup", "sales": "sale"}
SNIPPET_MAX_PER_REQUEST = 1

# Per-post analysis (vs the creator's usual views and engagement)
TRENDING_FROM = 2.0  # views ≥ 2× their usual: "Trending"
ABOVE_FROM = 1.2
BELOW_UNDER = 0.6
SMALL_CHANNEL_VIEWS = 5000  # "smaller channels" in insights: usual views under this
INSIGHT_MIN_POSTS = 2  # an insight that compares groups needs at least this many live posts in each
