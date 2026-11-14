"""Creator database settings (spec §4.4, §4.9, §4.14)."""

from datetime import timedelta

# Reuse a stored profile (followers, bio, links) for this long; posts are always fetched fresh.
PROFILE_MAX_AGE = timedelta(days=7)

# YouTube API policy: stored API data must be refreshed or deleted after about 30 days
# (confirm the current policy text). Other platforms have no forced expiry.
DATA_TTL = {"youtube": timedelta(days=30)}

# Embeddings for "similar creator" search (pgvector).
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768  # gemini-embedding-001 supports 768 output dims; HNSW indexes allow up to 2000

# Linking one person's accounts across platforms.
LINK_SELF = "self_link"  # the account links to the other account itself: verified
LINK_REVERSE = "reverse_link"  # the other account links back
LINK_NAME_MATCH = "name_match"  # same name/handle, no link: only a suggestion unless confirmed
AUTO_MERGE_SOURCES = {LINK_SELF, LINK_REVERSE}
NAME_MATCH_MERGE_FROM = 0.85  # Jev "same person?" probability needed to merge a name match
NAME_SIMILAR_FROM = 0.85  # code: names/handles this alike count as matching (difflib ratio after normalising)
ENRICH_TOP_PEOPLE = 10  # after a search, the other accounts of this many top people are measured automatically
MAX_SAME_PERSON_CHECKS = 30  # Jev "same person?" checks per search (pairs that code found worth asking)

# Nightly YouTube refresh (spec §4.4, roadmap F1.11). Creators due within REFRESH_AHEAD are refreshed
# if they're useful (scored in a run or in someone's results/saved leads); the rest are deleted once
# expired. A refresh costs about 1 quota unit per creator (uploads list) + 2 per 50 (channels, videos),
# so 1,400 creators is ~1,460 of the 10,000 daily units.
REFRESH_AHEAD = timedelta(days=2)
REFRESH_MAX_CREATORS = 1400
REFRESH_SCAN_LIMIT = 5000
REFRESH_CRON = "17 9 * * *"  # daily, 09:17 UTC: after YouTube's quota day starts (midnight Pacific)

# Older results saved without profile photos get them added by the nightly job (1 quota unit per 50).
AVATAR_BACKFILL_MAX = 2000
