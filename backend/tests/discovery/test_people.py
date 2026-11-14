"""The "people" step (roadmap F1.17b) with Jev and the platform adapters simulated: links published by the
creators merge accounts, a sponsor's link never does, a same-name account is only "probably also" after Jev
agrees, the top people's other accounts get measured, and each person is one result."""

from datetime import datetime, timezone

import pytest

from app.creators import repository as repo
from app.discovery.people import link_people
from app.discovery.people_cards import accounts_for
from app.judge.client import Answer, Judgment
from app.metrics.compute import BriefContext
from app.platforms.base import CreatorProfile
from tests.shared_core.factories import post

pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def prof(platform, pid, name, handle, links=None, followers=50_000, **kw) -> CreatorProfile:
    return CreatorProfile(platform=platform, platform_id=pid, handle=handle, display_name=name, bio="I teach coding.",
                          url=kw.pop("url", f"https://{platform}.com/{handle}"), followers=followers,
                          cross_links=links or {}, external_links=[], contacts={}, recent_posts=[post(i) for i in range(6)],
                          country="US", **kw)


async def save(p, sf):
    cid = await repo.upsert_profile(p, session_factory=sf)
    await repo.save_snapshot(cid, p, {"median_views": 9000.0, "engagement_rate": 0.03, "valuation": 120.0,
                                      "fair_low": 90.0, "fair_high": 150.0}, session_factory=sf)
    return cid


def judge_says(same_names: set):
    calls = []

    async def judge(state, questions):
        a, b = state["account_a"]["name"], state["account_b"]["name"]
        calls.append((a, b))
        same = 0.95 if {a, b} <= same_names else 0.05
        return Judgment({"same_person": Answer("noul", same), "injection": Answer("noul", 0.0)}, "jev", "jev")
    judge.calls = calls
    return judge


class FakeXAdapter:
    def __init__(self):
        self.api = self
        self.fetched = []

    async def user_info(self, handle):
        return {"data": {"id": "999", "userName": handle}}

    async def fetch_profiles(self, refs, constraints=None, max_deep=None):
        self.fetched += [r.platform_id for r in refs]
        return [prof("x", "999", "Sofia Codes", "sofiacodes", url="https://x.com/sofiacodes",
                     links={"youtube": "https://www.youtube.com/@SofiaCodes"})]


async def test_people_step_links_checks_and_measures(sf):
    yt = await save(prof("youtube", "UCsofia000000000000000000", "Sofia Codes", "@SofiaCodes",
                         url="https://www.youtube.com/@SofiaCodes",
                         links={"instagram": "https://instagram.com/sofia.codes",  # her own Instagram (links back)
                                "x": "https://x.com/sofiacodes",                   # her X: not measured yet
                                "linkedin": "https://linkedin.com/in/notion-team"}), sf)  # a sponsor's page
    ig = await save(prof("instagram", "sofia.codes", "Totally rebranded", "sofia.codes",
                         links={"youtube": "https://www.youtube.com/@SofiaCodes"}), sf)
    sponsor = await save(prof("linkedin", "notion-team", "Notion", "notion-team"), sf)
    twin = await save(prof("linkedin", "mike-chen", "Mike Chen", "mike-chen"), sf)
    other = await save(prof("youtube", "UCmike0000000000000000000", "Mike Chen", "@MikeChenCooks"), sf)
    x = FakeXAdapter()
    judge = judge_says({"Mike Chen"})
    ranked = [{"creator_id": c, "final_score": s} for c, s in ((yt, 80), (other, 70), (twin, 60))]

    stats = await link_people(ranked, adapters={"x": lambda: x}, judge=judge, metrics_ctx=BriefContext(),
                              session_factory=sf, now=NOW)

    people = await repo.people_of([yt, ig, other, twin, sponsor], session_factory=sf)
    assert people[yt]["person_id"] and people[yt]["person_id"] == people[ig]["person_id"]  # linked both ways
    assert people[sponsor]["person_id"] != people[yt]["person_id"]  # a sponsor's link never merges
    assert ("Sofia Codes", "Notion") in judge.calls  # ...it was only a question for Jev, who said no
    assert x.fetched == ["999"] and stats["measured"] == 1  # her X was measured for this top person
    sofia_accounts = {a["creator_id"]: a["status"] for a in people[yt]["accounts"]}
    assert ig in sofia_accounts and len([s for s in sofia_accounts.values() if s == "linked"]) == 2  # Instagram + X
    # same name, no link: only "probably also", never merged
    assert people[other]["person_id"] != people[twin]["person_id"] or people[twin]["person_id"] is None
    assert {a["status"] for a in people[other]["accounts"]} == {"suggested"}
    assert stats["linked"] >= 2 and stats["suggested"] == 1


async def test_cards_show_one_row_per_platform_with_statuses(sf):
    yt = await save(prof("youtube", "UCsofia000000000000000000", "Sofia Codes", "@SofiaCodes",
                         url="https://www.youtube.com/@SofiaCodes",
                         links={"instagram": "https://instagram.com/sofia.codes", "linkedin": "https://linkedin.com/in/sofia-c"}), sf)
    ig = await save(prof("instagram", "sofia.codes", "Sofia", "sofia.codes", followers=12_000,
                         links={"youtube": "https://www.youtube.com/@SofiaCodes"}), sf)
    await repo.link_accounts(yt, ig, source="self_link", session_factory=sf)
    main = (await repo.get_creators([yt], session_factory=sf))[yt]
    cards = await accounts_for(main, scored={yt: {"final_score": 81.5}}, session_factory=sf)
    assert [(c["platform"], c["status"]) for c in cards] == [("youtube", "main"), ("instagram", "linked"), ("linkedin", "unmeasured")]
    assert cards[0]["score"] == 81.5 and cards[1]["followers"] == 12_000 and cards[1]["avg_views"] == 9000
    assert cards[2]["url"] == "https://linkedin.com/in/sofia-c" and cards[2]["measured"] is False


async def test_a_judge_outage_links_nothing_uncertain(sf):
    a = await save(prof("youtube", "UCmike0000000000000000000", "Mike Chen", "@MikeChenCooks"), sf)
    b = await save(prof("linkedin", "mike-chen", "Mike Chen", "mike-chen"), sf)

    async def down(state, questions):
        raise RuntimeError("Jev down")

    stats = await link_people([{"creator_id": a}, {"creator_id": b}], adapters={}, judge=down,
                              metrics_ctx=BriefContext(), session_factory=sf, now=NOW)
    people = await repo.people_of([a, b], session_factory=sf)
    assert stats["suggested"] == 0 and people[a]["accounts"] == []
