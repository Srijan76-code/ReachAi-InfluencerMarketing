"""Nightly YouTube refresh (F1.11): refresh useful creators, delete the rest after 30 days, clean old copies,
and update or expire old results. Runs on SQLite, and on Postgres when PG_TEST_URL is set."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.creators import constants as C
from app.creators import repository as repo
from app.creators.refresh import run_refresh
from app.models.campaign import Campaign
from app.models.creator import Creator, CreatorSnapshot
from app.models.discovery_run import RunCandidate
from app.models.saved_lead import SavedLead
from app.models.user import User
from tests.discovery.conftest import TABLES, create_tables, make_engine
from tests.discovery.fakes import BRIEF
from tests.shared_core.factories import post

NOW = datetime.now(timezone.utc)  # the repository stamps real time, so tests use it too


@pytest_asyncio.fixture
async def sf(tmp_path):
    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, ["users", "campaigns", "saved_leads"] + TABLES)
    yield sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


def yt(pid, followers=50_000, name=None):
    posts = [post(i, views=20_000, days_ago=2 + i * 5, text=f"{pid} video {i}") for i in range(10)]
    for i, p in enumerate(posts):
        p["published_at"] = NOW - timedelta(days=2 + i * 5)
    return {"platform": "youtube", "platform_id": pid, "display_name": name or f"Creator {pid}", "bio": f"bio {pid}",
            "url": f"https://www.youtube.com/channel/{pid}", "followers": followers, "country": "IN",
            "recent_posts": posts, "fetched_at": NOW, "platform_stats": {"video_count": 120, "uploads_playlist": f"UU{pid}"}}


async def seed(sf, pid, expires_in_days, useful=None):
    cid = await repo.upsert_profile(yt(pid), session_factory=sf)
    async with sf() as s:
        await s.execute(update(Creator).where(Creator.creator_id == cid).values(data_expires_at=NOW + timedelta(days=expires_in_days)))
        if useful == "scored":
            s.add(RunCandidate(run_id="r1", creator_id=cid, platform="youtube", stage="scored", metrics={"m": 1}))
        await s.commit()
    return cid


class FakeAdapter:
    def __init__(self, returns: dict, *, quota=False, raises=False):
        self.returns, self.quota, self.raises = returns, quota, raises
        self.warnings, self._quota_exhausted, self.asked = [], quota, []

    async def fetch_profiles(self, refs, constraints=None):
        self.asked.append([r.platform_id for r in refs])
        if self.raises:
            raise RuntimeError("network down")
        if self.quota:
            self.warnings.append("YouTube's daily limit was reached")
        return [self.returns[r.platform_id] for r in refs if r.platform_id in self.returns]


def lead(pid, as_of_days_ago, **extra):
    return {"id": pid, "title": f"Creator {pid}", "subscribers": 1, "description": "old", "country": "IN",
            "metrics": {"avg_views": 1, "volatility": 0, "reliability": "Low", "engagement_rate": 1, "raw_engagement": 0.01,
                        "trust_score": 1, "forecast": "~1 clicks/video"},
            "socials": {"email": "x@example.com", "instagram": None, "twitter": None, "linkedin": None},
            "recent_videos": [{"title": "old", "views": 1}], "valuation": 1, "final_score": 70, "deal_status": "Consider",
            "llm_reasoning": "our reason", "score_breakdown": {"strategy_score": 70, "health_score": 60, "risk_penalty": "Low"},
            "data_as_of": (NOW - timedelta(days=as_of_days_ago)).isoformat(), **extra}


@pytest_asyncio.fixture
async def world(sf):
    ids = {
        "useful": await seed(sf, "UCuseful", 1, useful="scored"),  # due, scored in a run -> refreshed
        "idle_expired": await seed(sf, "UCidle", -1),  # expired, in no run or results -> deleted
        "idle_due": await seed(sf, "UCsoon", 1),  # due tomorrow, not useful -> kept until it expires
        "gone": await seed(sf, "UCgone", 1),  # due, saved by a user, YouTube no longer returns it -> deleted
        "later": await seed(sf, "UClater", 20),  # not due
    }
    async with sf() as s:
        s.add(User(user_id="u1", clerk_id="c1"))
        await s.flush()
        s.add(Campaign(campaign_id="c1", user_id="u1", campaign_details=BRIEF, campaign_leads=[
            lead("UCuseful", 40), lead("UCold", 40), lead("UClater", 5), {"id": "x-not-youtube", "title": "other"}]))
        await s.flush()
        s.add(SavedLead(lead_id="s1", campaign_id="c1", name="gone", lead_data=lead("UCgone", 35)))
        # copies older than 30 days
        s.add(CreatorSnapshot(creator_id=ids["later"], captured_at=NOW - timedelta(days=40), followers=1, recent_posts=[]))
        s.add(RunCandidate(run_id="old", creator_id=ids["later"], platform="youtube", stage="measured", metrics={"m": 1},
                           created_at=NOW - timedelta(days=40)))
        await s.commit()
    return ids


@pytest.mark.asyncio
async def test_nightly_refresh_end_to_end(sf, world):
    adapter = FakeAdapter({"UCuseful": yt("UCuseful", followers=99_000, name="Renamed Creator")})
    report = await run_refresh(adapter_factory=lambda: adapter, session_factory=sf)

    # only useful creators cost quota: due + useful, plus the unstored creator from an old result
    assert sorted(adapter.asked[0]) == ["UCgone", "UCold", "UCuseful"]
    assert report.refreshed == 1 and report.gone_on_youtube == 1 and report.deleted == 2
    async with sf() as s:
        rows = {r.platform_id: r for r in (await s.execute(select(Creator))).scalars()}
        snaps = (await s.execute(select(CreatorSnapshot).where(CreatorSnapshot.creator_id == world["later"]))).scalars().all()
        old_run = (await s.execute(select(RunCandidate).where(RunCandidate.run_id == "old"))).scalar_one()
        new_run = (await s.execute(select(RunCandidate).where(RunCandidate.run_id == "r1"))).scalar_one()
        camp = (await s.execute(select(Campaign))).scalar_one()
        saved = (await s.execute(select(SavedLead))).scalar_one()

    assert set(rows) == {"UCuseful", "UCsoon", "UClater"}  # idle-expired and gone are deleted
    renewed = rows["UCuseful"].data_expires_at
    renewed = renewed if renewed.tzinfo else renewed.replace(tzinfo=timezone.utc)
    assert renewed > NOW + timedelta(days=29) and rows["UCuseful"].followers == 99_000
    assert snaps == [] and report.snapshots_deleted >= 1  # 40-day-old snapshot removed
    assert old_run.metrics is None and new_run.metrics == {"m": 1}  # only old run records lose copied numbers

    by_id = {l["id"]: l for l in camp.campaign_leads}
    up = by_id["UCuseful"]
    assert up["subscribers"] == 99_000 and up["title"] == "Renamed Creator" and up["recent_videos"][0]["title"].startswith("UCuseful")
    assert up["final_score"] == 70 and up["llm_reasoning"] == "our reason"  # our scores and text are kept
    assert "data_expired" not in up and datetime.fromisoformat(up["data_as_of"]) > NOW - timedelta(minutes=5)
    gone = by_id["UCold"]  # an old-engine result whose creator was never stored: nothing to refresh from
    assert gone["data_expired"] and gone["subscribers"] == 0 and gone["recent_videos"] == [] and gone["socials"]["email"] is None
    assert gone["title"] == "Creator UCold" and gone["final_score"] == 70  # name, link and our scores stay
    assert by_id["UClater"]["subscribers"] == 1  # under 30 days old: untouched
    assert by_id["x-not-youtube"] == {"id": "x-not-youtube", "title": "other"}
    assert saved.lead_data["data_expired"] and saved.lead_data["subscribers"] == 0
    assert report.leads_updated == 1 and report.leads_expired == 2


@pytest.mark.asyncio
async def test_quota_hit_does_not_treat_creators_as_gone(sf, world):
    adapter = FakeAdapter({}, quota=True)
    report = await run_refresh(adapter_factory=lambda: adapter, session_factory=sf)
    async with sf() as s:
        left = set((await s.execute(select(Creator.platform_id))).scalars())
    assert report.gone_on_youtube == 0 and report.refreshed == 0
    assert left == {"UCuseful", "UCsoon", "UCgone", "UClater"}  # only the expired one is deleted
    assert report.warnings


@pytest.mark.asyncio
async def test_failed_fetch_still_deletes_expired_data(sf, world):
    report = await run_refresh(adapter_factory=lambda: FakeAdapter({}, raises=True), session_factory=sf)
    async with sf() as s:
        left = set((await s.execute(select(Creator.platform_id))).scalars())
    assert "UCidle" not in left and "UCuseful" in left and "UCgone" in left
    assert any("refresh failed" in w for w in report.warnings)


@pytest.mark.asyncio
async def test_refresh_cap_limits_quota(sf, world, monkeypatch):
    monkeypatch.setattr(C, "REFRESH_MAX_CREATORS", 1)
    adapter = FakeAdapter({"UCuseful": yt("UCuseful"), "UCgone": yt("UCgone")})
    report = await run_refresh(adapter_factory=lambda: adapter, session_factory=sf)
    assert len(adapter.asked[0]) == 1 and report.skipped_over_cap == 2  # 2 due + 1 old result, room for 1


@pytest.mark.asyncio
async def test_nothing_due_is_a_cheap_no_op(sf):
    calls = []
    report = await run_refresh(adapter_factory=lambda: calls.append(1), session_factory=sf)
    assert calls == [] and report.due == 0 and report.deleted == 0


@pytest.mark.asyncio
async def test_running_twice_changes_nothing_more(sf, world):
    adapter = FakeAdapter({"UCuseful": yt("UCuseful")})
    await run_refresh(adapter_factory=lambda: adapter, session_factory=sf)
    async with sf() as s:
        before = (await s.execute(select(Campaign))).scalar_one().campaign_leads
    second = await run_refresh(adapter_factory=lambda: FakeAdapter({}), session_factory=sf)
    async with sf() as s:
        after = (await s.execute(select(Campaign))).scalar_one().campaign_leads
    assert second.deleted == 0 and second.leads_updated == 0 and second.leads_expired == 0
    assert before == after


@pytest.mark.asyncio
async def test_old_engine_results_are_refreshed_and_their_creators_stored(sf, world):
    """The old engine never stored creators; their old results are fetched again instead of emptied."""
    adapter = FakeAdapter({"UCuseful": yt("UCuseful"), "UCold": yt("UCold", followers=77_000)})
    report = await run_refresh(adapter_factory=lambda: adapter, session_factory=sf)
    async with sf() as s:
        camp = (await s.execute(select(Campaign))).scalar_one()
        stored = set((await s.execute(select(Creator.platform_id))).scalars())
    old = {l["id"]: l for l in camp.campaign_leads}["UCold"]
    assert old["subscribers"] == 77_000 and "data_expired" not in old
    assert "UCold" in stored  # now in the creator database, so tomorrow it's a normal refresh
    assert report.leads_updated == 2 and report.leads_expired == 1  # only the saved lead of the vanished channel


@pytest.mark.asyncio
@pytest.mark.skipif(not __import__("os").getenv("PG_TEST_URL"), reason="needs PG_TEST_URL (real Postgres)")
async def test_old_checkpoint_threads_are_purged_recent_ones_kept():
    import os
    from typing import TypedDict

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.graph import END, START, StateGraph

    from app.creators.refresh import purge_old_checkpoints

    class S(TypedDict, total=False):
        x: int

    g = StateGraph(S)
    g.add_node("step", lambda s: {"x": 1})
    g.add_edge(START, "step")
    g.add_edge("step", END)
    url = os.environ["PG_TEST_URL"].replace("+asyncpg", "")
    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        await saver.setup()
        app = g.compile(checkpointer=saver)
        for t in ("old-thread", "new-thread"):
            await saver.adelete_thread(t)
            await app.ainvoke({"x": 0}, {"configurable": {"thread_id": t}})
        old_ts = (NOW - timedelta(days=40)).isoformat()
        async with saver.conn.cursor() as cur:
            await cur.execute("UPDATE checkpoints SET checkpoint = jsonb_set(checkpoint, '{ts}', to_jsonb(%s::text)) "
                              "WHERE thread_id = 'old-thread'", (old_ts,))
        deleted = await purge_old_checkpoints(saver, now=NOW)
        assert deleted >= 1
        assert await saver.aget_tuple({"configurable": {"thread_id": "old-thread"}}) is None
        assert await saver.aget_tuple({"configurable": {"thread_id": "new-thread"}}) is not None
        async with saver.conn.cursor() as cur:
            await cur.execute("SELECT count(*) AS n FROM checkpoint_writes WHERE thread_id = 'old-thread'")
            row = await cur.fetchone()
            assert (row["n"] if isinstance(row, dict) else row[0]) == 0
        await saver.adelete_thread("new-thread")


@pytest.mark.asyncio
async def test_results_without_photos_get_them_added(sf, world):
    class PhotoAdapter(FakeAdapter):
        async def fetch_avatars(self, ids):
            self.photo_ids = list(ids)
            return {i: f"https://yt3/{i}" for i in ids if i != "UCgone"}

    adapter = PhotoAdapter({"UCuseful": yt("UCuseful")})
    report = await run_refresh(adapter_factory=lambda: adapter, session_factory=sf)
    async with sf() as s:
        camp = (await s.execute(select(Campaign))).scalar_one()
    by_id = {l["id"]: l for l in camp.campaign_leads}
    assert by_id["UClater"]["avatar_url"] == "https://yt3/UClater"  # a recent result gets its photo
    assert "avatar_url" not in by_id["UCold"]  # expired results stay without YouTube data
    assert "x-not-youtube" not in adapter.photo_ids and "UCold" not in adapter.photo_ids
    assert report.avatars_added >= 1
    again = await run_refresh(adapter_factory=lambda: PhotoAdapter({}), session_factory=sf)
    assert again.avatars_added == 0  # nothing left to fill


def test_refreshed_lead_keeps_brief_topics_and_our_score_parts():
    """Refreshed posts are re-tagged against the same brief topics; the score breakdown is ours and stays."""
    from app.creators.refresh import _refreshed_lead
    from app.metrics.compute import BriefContext

    lead = {"id": "UC1", "final_score": 70, "match_terms": ["UC1 video"], "score_parts": {"fit": 40.0},
            "posts": [], "signals": {"posts_checked": 0}}
    out = _refreshed_lead(lead, yt("UC1"), "other", BriefContext(), NOW)
    assert out["match_terms"] == ["UC1 video"] and out["score_parts"] == {"fit": 40.0} and out["final_score"] == 70
    assert out["signals"]["posts_checked"] == 10 and out["signals"]["fit_posts"] == 10
    assert out["posts"][0]["matched_topics"] == ["UC1 video"] and out["posts"][2]["x_usual"] == 1.0
    assert out["posts"][0]["is_new"] and out["posts"][0]["x_usual"] is None  # 2 days old: still collecting views
