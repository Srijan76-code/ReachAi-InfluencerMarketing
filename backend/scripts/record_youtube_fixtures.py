"""Record real YouTube responses for the adapter tests.

    cd backend && python -m scripts.record_youtube_fixtures

Uses YOUTUBE_API_KEY and about 220 quota units (2 searches + a few lookups).
Writes tests/fixtures/youtube/recording.json with email addresses replaced.
"""

import asyncio
import json
from datetime import datetime, timezone

from app.billing import costs
from app.platforms.base import Limits, Strategy
from app.platforms.youtube import YouTubeAdapter
from app.platforms.youtube_api import HttpYouTubeAPI
from tests.platforms.youtube_replay import FIXTURE, RecordingAPI

RECORDED_AT = datetime(2026, 11, 3, tzinfo=timezone.utc)
STRATEGY = Strategy(
    topics=["data science career"],
    pain_points=["getting a first ML job"],
    queries={"youtube": ["machine learning roadmap for freshers"]},
)
LIMITS = Limits(max_queries=2, max_candidates=8, max_profiles=8, region="IN", published_within_days=21)
CONSTRAINTS = {"min_subscribers": 10_000, "max_subscribers": 5_000_000}


async def _no_cache(namespace, key, ttl, compute):
    return await compute(), False


async def main():
    async def no_db(record):  # don't need a database to record
        return None

    costs.set_sink(no_db)
    http = HttpYouTubeAPI()
    api = RecordingAPI(http)
    adapter = YouTubeAdapter(api, cache=_no_cache, now=lambda: RECORDED_AT)
    refs = await adapter.source_candidates(STRATEGY, LIMITS)
    profiles = await adapter.fetch_profiles(refs, CONSTRAINTS)
    await http.aclose()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps({"recorded_at": RECORDED_AT.isoformat(), "calls": api.calls}, indent=1, ensure_ascii=False))
    print(f"recorded {len(api.calls)} calls, {http.units_used} quota units, {len(refs)} candidates, "
          f"{len(profiles)} profiles kept, {len(adapter.dropped)} dropped, warnings={adapter.warnings}")


if __name__ == "__main__":
    asyncio.run(main())
