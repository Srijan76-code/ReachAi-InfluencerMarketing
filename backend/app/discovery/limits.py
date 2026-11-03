"""Every limit and budget of a discovery run (spec §4.9, §4.14). Tune here, nowhere else."""

from app.platforms.base import Limits

# Search budget per platform branch mode
LIMITS_BY_MODE = {
    "full": Limits(max_queries=8, max_candidates=300, max_profiles=150, published_within_days=21),
    "probe": Limits(max_queries=2, max_candidates=60, max_profiles=30, published_within_days=21),
    "expand": Limits(max_queries=6, max_candidates=240, max_profiles=120, published_within_days=21),
}

# Top-up round (full branches only): if fewer than TOPUP_FACTOR x the creators asked for pass the
# checks, search once more: unused queries first, all-time video search ordered by views (larger creators).
TOPUP_FACTOR = 10
TOPUP_LIMITS = Limits(max_queries=3, max_candidates=150, max_profiles=100, published_within_days=None, order="viewCount")

SHORTLIST_SIZE = 100  # creators per branch that go to Jev
SHORTLIST_EMBED_WEIGHT = 0.7  # hybrid shortlist: 70% embedding similarity, 30% keyword (BM25)
DB_SEARCH_LIMIT = 100  # creators from our own database per run
FIT_FLOOR = 0.55  # if the top creators' mean fit is below this, expand every probe platform
FINAL_LIST_MAX = 50  # creators returned to the results screen
REASON_CONCURRENCY = 5

# Inngest (spec §4.14)
RUNS_PER_USER = 2
RUNS_PER_ACCOUNT = 10
RUN_RETRIES = 3
RUN_TIMEOUT_MINUTES = 15
