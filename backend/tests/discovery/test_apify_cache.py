"""The Apify adapters' cache and run memo on the real cache table (a miss is the cache's _MISS marker, not None).
Regression: on Nov 13 every Instagram and LinkedIn search failed with a TypeError because a miss was read as a hit."""

import pytest

from app.platforms.apify import DbStore, db_memo
from app.platforms.base import Limits, Strategy
from app.platforms.instagram import InstagramAdapter
from app.platforms.linkedin import LinkedInAdapter
from tests.platforms.test_instagram import ReplayApify as IgReplay
from tests.platforms.test_linkedin import ReplayApify as LiReplay

pytestmark = pytest.mark.asyncio
LIMITS = Limits(max_queries=1, max_candidates=50, max_profiles=5)


async def test_store_returns_none_on_a_miss_and_the_value_on_a_hit(sf):
    store = DbStore(lambda: sf)
    assert await store.get("search", {"q": "x"}) is None
    from datetime import timedelta

    await store.set("search", {"q": "x"}, ["a", "b"], timedelta(hours=1))
    assert await store.get("search", {"q": "x"}) == ["a", "b"]


async def test_run_memo_misses_then_remembers(sf):
    memo = db_memo(lambda: sf)
    assert await memo.get("actor|input|run") is None
    await memo.set("actor|input|run", "run123")
    assert await memo.get("actor|input|run") == "run123"


async def test_a_broken_cache_counts_as_a_miss():
    def broken():
        raise RuntimeError("database down")

    store, memo = DbStore(broken), db_memo(broken)
    assert await store.get("search", "k") is None and await memo.get("k") is None
    await store.set("search", "k", 1, None)  # no error
    await memo.set("k", "v")


async def test_instagram_and_linkedin_search_end_to_end_on_the_real_cache(sf):
    ig = InstagramAdapter(IgReplay(), store=DbStore(lambda: sf))
    refs = await ig.source_candidates(Strategy(topics=[], pain_points=[], queries={"instagram": ["ai tools"]}), LIMITS)
    assert refs and not ig.warnings
    profiles = await ig.fetch_profiles([r for r in refs if r.platform_id == "opusjake"] or refs[:1], {"min_subscribers": 0})
    assert profiles is not None

    li = LinkedInAdapter(LiReplay(), store=DbStore(lambda: sf))
    refs = await li.source_candidates(Strategy(topics=[], pain_points=[], queries={"linkedin": ["devops"]}), LIMITS)
    assert refs and not li.warnings
    again = LiReplay()
    li2 = LinkedInAdapter(again, store=DbStore(lambda: sf))
    await li2.source_candidates(Strategy(topics=[], pain_points=[], queries={"linkedin": ["devops"]}), LIMITS)
    assert not again.calls  # second search read the cache
