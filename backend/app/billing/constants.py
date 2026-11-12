"""Credits and plans (spec §5). Change prices here only; never inline them elsewhere."""

from datetime import timedelta

# Credits for one creator search on one platform (≈ our measured cost × 2, rounded). Reviewed quarterly from
# cost_events. A change never applies to a search that has already started (its reservation is fixed).
SEARCH_CREDITS: dict[str, int] = {"youtube": 1, "x": 3, "instagram": 4, "linkedin": 8}

# Platforms that can actually be searched today. A search is charged only for these.
LIVE_PLATFORMS: tuple[str, ...] = ("youtube",)

# Running a campaign again ("Find more") reuses cached data, so it costs this share, rounded up.
FIND_MORE_FACTOR = 0.5

# Plans: monthly credits and whether unused monthly credits roll over for one month.
PLANS: dict[str, dict] = {
    "free": {"monthly": 3, "rollover": False},
    "solo": {"monthly": 25, "rollover": True},
    "pro": {"monthly": 80, "rollover": True},
}
DEFAULT_PLAN = "free"

# One-time credits for every new account (not for referrals; those are separate).
WELCOME_CREDITS = 5

# A search that finds fewer creators than this is refunded automatically.
GUARANTEE_MIN_CREATORS = 10

# Buckets, in the order credits are spent: the ones that expire first go first.
BUCKETS: tuple[str, ...] = ("monthly", "rollover", "bonus", "pack")

# A held reservation is released if its run hasn't finished by then (the run itself times out much sooner).
RESERVATION_TTL = timedelta(hours=3)
RELEASE_CRON = "23 * * * *"  # hourly sweep of stale reservations

# Searches one user can start in 24 hours, from any source (web or agents).
MAX_SEARCHES_PER_DAY = 20
