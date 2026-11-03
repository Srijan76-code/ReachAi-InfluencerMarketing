import math
from datetime import timedelta

import pytest

from app.creators import constants as C
from app.creators import repository as repo
from app.judge.questions import JudgeBrief
from tests.shared_core.factories import NOW, post, profile


def yt(pid="UC1", followers=200_000, **kw):
    return profile(platform_id=pid, followers=followers, fetched_at=NOW, source="youtube_api", **kw)


def vec(*hot, dim=C.EMBEDDING_DIM):
    """Unit-ish vector with the given positions set (easy to reason about cosine)."""
    v = [0.0] * dim
    for i in hot:
        v[i] = 1.0
    return v


# --- profiles -----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_inserts_then_updates_same_account(db):
    cid = await repo.upsert_profile(yt(), session_factory=db)
    again = await repo.upsert_profile({**yt(), "followers": 250_000, "bio": "new bio"}, session_factory=db)
    assert cid == again
    stored = await repo.get_creator(cid, session_factory=db)
    assert stored["followers"] == 250_000 and stored["bio"] == "new bio"
    assert await repo.count_creators(session_factory=db) == 1


@pytest.mark.asyncio
async def test_upsert_requires_identity(db):
    with pytest.raises(ValueError):
        await repo.upsert_profile({"platform": "youtube"}, session_factory=db)


@pytest.mark.asyncio
async def test_youtube_rows_expire_after_30_days_others_do_not(db):
    yt_id = await repo.upsert_profile(yt(), session_factory=db)
    x_id = await repo.upsert_profile({**yt("x1"), "platform": "x"}, session_factory=db)
    later = repo._now() + timedelta(days=31)
    expired = await repo.expired_creator_ids(now=later, session_factory=db)
    assert yt_id in expired and x_id not in expired
    assert await repo.expired_creator_ids(session_factory=db) == []


@pytest.mark.asyncio
async def test_split_fresh_reuses_recent_profiles_only(db):
    await repo.upsert_profile(yt("fresh"), session_factory=db)
    await repo.upsert_profile({**yt("old"), "fetched_at": NOW - timedelta(days=10)}, session_factory=db)
    split = await repo.split_fresh("youtube", ["fresh", "old", "new", "fresh"], now=NOW, session_factory=db)
    assert set(split.fresh) == {"fresh"}
    assert split.to_fetch == ["old", "new"]  # duplicates removed, order kept
    assert split.fresh["fresh"]["recent_posts"] == []  # posts are always fetched fresh
    assert (await repo.split_fresh("youtube", [], session_factory=db)).to_fetch == []


@pytest.mark.asyncio
async def test_split_fresh_skips_expired_rows(db):
    await repo.upsert_profile(yt("e1"), session_factory=db)
    after_expiry = repo._now() + C.DATA_TTL["youtube"] + timedelta(days=1)
    split = await repo.split_fresh("youtube", ["e1"], now=after_expiry, max_age=timedelta(days=365), session_factory=db)
    assert split.to_fetch == ["e1"]


@pytest.mark.asyncio
async def test_snapshot_stores_posts_and_latest_metrics(db):
    cid = await repo.upsert_profile(yt(), session_factory=db)
    await repo.save_snapshot(cid, yt(), {"engagement_rate": 0.042, "median_views": 12000.0}, session_factory=db)
    stored = await repo.get_creator(cid, session_factory=db)
    assert len(stored["recent_posts"]) == 15  # datetimes serialised safely
    assert await repo.peer_engagement("youtube", "mid", session_factory=db) == [0.042]
    assert await repo.peer_engagement("youtube", "nano", session_factory=db) == []
    rows = await repo.anomaly_training_rows("youtube", session_factory=db)
    assert rows[0]["median_views"] == 12000.0


@pytest.mark.asyncio
async def test_get_missing_creator_returns_none(db):
    assert await repo.get_creator("nope", session_factory=db) is None


# --- Jev answer cache ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_judgment_cache_hits_only_on_same_content_brief_and_version(db):
    cid = await repo.upsert_profile(yt(), session_factory=db)
    p = yt()
    brief = JudgeBrief(product="Bootcamp", persona="Grads")
    ch, bh = repo.content_hash(p), repo.brief_hash(brief)
    answers = {"model": "jev-1.13.0", "source": "jev", "input_tokens": 1500, "answers": {"is_individual": {"type": "noul", "value": 0.9}}}
    await repo.save_judgment(cid, ch, bh, "creator-v1", answers, session_factory=db)
    await repo.save_judgment(cid, ch, bh, "creator-v1", answers, session_factory=db)  # duplicate is ignored
    assert (await repo.get_cached_judgment(cid, ch, bh, "creator-v1", session_factory=db))["answers"]["is_individual"]["value"] == 0.9
    assert await repo.get_cached_judgment(cid, ch, bh, "creator-v2", session_factory=db) is None
    changed = {**p, "recent_posts": [post(0, text="A totally new video")]}
    assert await repo.get_cached_judgment(cid, repo.content_hash(changed), bh, "creator-v1", session_factory=db) is None
    other_brief = repo.brief_hash(JudgeBrief(product="Other", persona="Grads"))
    assert await repo.get_cached_judgment(cid, ch, other_brief, "creator-v1", session_factory=db) is None


@pytest.mark.asyncio
async def test_llm_fallback_answers_are_not_cached(db):
    cid = await repo.upsert_profile(yt(), session_factory=db)
    await repo.save_judgment(cid, "c", "b", "creator-v1", {"source": "llm_fallback", "answers": {}}, session_factory=db)
    assert await repo.get_cached_judgment(cid, "c", "b", "creator-v1", session_factory=db) is None


def test_content_hash_ignores_numbers_but_tracks_text():
    a = yt()
    assert repo.content_hash(a) == repo.content_hash({**a, "followers": 1})
    assert repo.content_hash(a) != repo.content_hash({**a, "bio": "different"})


# --- embeddings + similar creators -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embedding_round_trip_and_staleness(db):
    cid = await repo.upsert_profile(yt(), session_factory=db)
    e = vec(1, 2)
    await repo.save_embedding(cid, e, "h1", session_factory=db)
    got = await repo.get_embedding(cid, "h1", session_factory=db)
    assert got is not None and math.isclose(got[1], 1.0) and len(got) == C.EMBEDDING_DIM
    assert await repo.get_embedding(cid, "h2", session_factory=db) is None  # text changed -> stale
    await repo.save_embedding(cid, vec(3), "h2", session_factory=db)  # replaces, doesn't duplicate
    assert await repo.get_embedding(cid, "h1", session_factory=db) is None
    assert (await repo.get_embedding(cid, "h2", session_factory=db))[3] == 1.0


@pytest.mark.asyncio
async def test_embedding_dimension_is_checked(db):
    cid = await repo.upsert_profile(yt(), session_factory=db)
    with pytest.raises(ValueError):
        await repo.save_embedding(cid, [0.1, 0.2], "h", session_factory=db)
    with pytest.raises(ValueError):
        await repo.similar_creators([0.1], session_factory=db)


@pytest.mark.asyncio
async def test_similar_creators_orders_by_cosine_and_filters(db):
    ids = {}
    for pid, followers, platform, hot in [
        ("same", 50_000, "youtube", (0,)),
        ("close", 80_000, "youtube", (0, 1)),
        ("far", 60_000, "youtube", (5,)),
        ("x_same", 70_000, "x", (0,)),
        ("tiny", 500, "youtube", (0,)),
    ]:
        cid = await repo.upsert_profile({**yt(pid, followers=followers), "platform": platform}, session_factory=db)
        await repo.save_embedding(cid, vec(*hot), f"h-{pid}", session_factory=db)
        ids[pid] = cid

    res = await repo.similar_creators(vec(0), platforms=["youtube"], min_followers=1000, session_factory=db)
    order = [r.platform_id for r in res]
    assert order == ["same", "close", "far"]
    assert res[0].similarity == pytest.approx(1.0, abs=1e-5)
    assert res[1].similarity == pytest.approx(1 / math.sqrt(2), abs=1e-5)
    assert res[2].similarity == pytest.approx(0.0, abs=1e-5)
    capped = await repo.similar_creators(vec(0), max_followers=60_000, limit=10, session_factory=db)
    assert {r.platform_id for r in capped} == {"same", "far", "tiny"}
    assert len(await repo.similar_creators(vec(0), limit=2, session_factory=db)) == 2
    assert await repo.similar_creators(vec(0), platforms=["linkedin"], session_factory=db) == []


# --- one person, several accounts ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_link_merges_accounts_into_one_person(db):
    a = await repo.upsert_profile(yt("yt_a"), session_factory=db)
    b = await repo.upsert_profile({**yt("ig_a"), "platform": "instagram"}, session_factory=db)
    person = await repo.link_accounts(a, b, source=C.LINK_SELF, session_factory=db)
    assert person
    accounts = await repo.person_accounts(person, session_factory=db)
    assert {p["platform"] for p in accounts} == {"youtube", "instagram"}


@pytest.mark.asyncio
async def test_weak_name_match_is_only_a_suggestion(db):
    from app.models.creator import PersonLink

    a = await repo.upsert_profile(yt("yt_b"), session_factory=db)
    b = await repo.upsert_profile({**yt("x_b"), "platform": "x"}, session_factory=db)

    assert await repo.link_accounts(a, b, source=C.LINK_NAME_MATCH, confidence=0.6, session_factory=db) is None
    assert (await repo.get_creator(b, session_factory=db)) is not None
    async with db() as s:
        link = await s.get(PersonLink, b)
    assert link.status == "suggested" and link.confidence == 0.6

    person = await repo.link_accounts(a, b, source=C.LINK_NAME_MATCH, confidence=0.9, session_factory=db)
    assert person is not None
    assert {p["platform"] for p in await repo.person_accounts(person, session_factory=db)} == {"youtube", "x"}
    async with db() as s:
        link = await s.get(PersonLink, b)
    assert link.status == "linked" and link.confidence == 0.9


@pytest.mark.asyncio
async def test_linking_merges_two_existing_people(db):
    a = await repo.upsert_profile(yt("p1"), session_factory=db)
    b = await repo.upsert_profile({**yt("p2"), "platform": "x"}, session_factory=db)
    c = await repo.upsert_profile({**yt("p3"), "platform": "instagram"}, session_factory=db)
    d = await repo.upsert_profile({**yt("p4"), "platform": "linkedin"}, session_factory=db)
    p_ab = await repo.link_accounts(a, b, source=C.LINK_SELF, session_factory=db)
    p_cd = await repo.link_accounts(c, d, source=C.LINK_SELF, session_factory=db)
    assert p_ab != p_cd
    merged = await repo.link_accounts(b, c, source=C.LINK_REVERSE, session_factory=db)
    assert len(await repo.person_accounts(merged, session_factory=db)) == 4


@pytest.mark.asyncio
async def test_link_rejects_bad_input(db):
    a = await repo.upsert_profile(yt("solo"), session_factory=db)
    with pytest.raises(ValueError):
        await repo.link_accounts(a, a, source=C.LINK_SELF, session_factory=db)
    with pytest.raises(ValueError):
        await repo.link_accounts(a, "missing", source=C.LINK_SELF, session_factory=db)


# --- deletion ---------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_creator_removes_everything(db):
    cid = await repo.upsert_profile(yt(), session_factory=db)
    other = await repo.upsert_profile({**yt("o"), "platform": "x"}, session_factory=db)
    await repo.save_snapshot(cid, yt(), {"engagement_rate": 0.03}, session_factory=db)
    await repo.save_embedding(cid, vec(0), "h", session_factory=db)
    await repo.save_judgment(cid, "c", "b", "v", {"source": "jev", "answers": {}}, session_factory=db)
    await repo.link_accounts(cid, other, source=C.LINK_SELF, session_factory=db)
    await repo.delete_creator(cid, session_factory=db)
    assert await repo.get_creator(cid, session_factory=db) is None
    assert await repo.get_embedding(cid, "h", session_factory=db) is None
    assert await repo.get_cached_judgment(cid, "c", "b", "v", session_factory=db) is None
    assert await repo.get_creator(other, session_factory=db) is not None
