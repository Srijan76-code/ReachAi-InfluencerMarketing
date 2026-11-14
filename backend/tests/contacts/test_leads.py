"""Saving found contacts on the campaign's leads, the creator and the deal; the 30-day cache; opt-outs and the
"contacted before" note (spec §7.1). The finder itself is simulated here (tested in test_find.py)."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.asyncio

TABLES = ["users", "campaigns", "creator_persons", "creators", "creator_snapshots", "creator_deals",
          "contact_history", "suppression_list"]


@pytest_asyncio.fixture
async def sf(tmp_path):
    from app.models import contact, creator, deal  # noqa: F401  (register tables)
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.creator import Creator
    from app.models.deal import CreatorDeal
    from app.models.user import User
    from tests.discovery.conftest import create_tables, make_engine

    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, TABLES)
    f = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    leads = [
        {"id": "UC1", "creator_id": "cr1", "title": "Priya Builds", "socials": {"email": "sponsor@acme.com"}},
        {"id": "UC2", "creator_id": "cr2", "title": "Sam Codes", "socials": {}},
        {"id": "UC3", "title": "Old lead", "description": "biz: old@lead.io", "socials": {"email": "old@lead.io"}},
    ]
    async with f() as s:
        s.add(User(user_id="u1", clerk_id="k1"))
        await s.flush()
        s.add(Campaign(campaign_id="c1", user_id="u1", name="T", campaign_details={}, campaign_leads=leads,
                       status=CampaignStatus.COMPLETED))
        s.add(Creator(creator_id="cr1", platform="youtube", platform_id="UC1", display_name="Priya Builds",
                      bio="I'm Priya", external_links=["https://linktr.ee/priya"], contacts={"emails": ["sponsor@acme.com"]}))
        recent = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        s.add(Creator(creator_id="cr2", platform="youtube", platform_id="UC2", display_name="Sam Codes",
                      contacts={"emails": [], "found": {"email": "sam@codes.dev", "email_source": "bio",
                                                        "first_name": "Sam", "searched_at": recent, "socials": {}}}))
        await s.flush()
        s.add(CreatorDeal(deal_id="d1", campaign_id="c1", creator_id="UC1", contact_email="sponsor@acme.com"))
        s.add(CreatorDeal(deal_id="d3", campaign_id="c1", creator_id="UC3", contact_email="typed@founder.com"))
        await s.commit()
    yield f
    await engine.dispose()


async def test_saves_results_and_reuses_recent_ones(sf, monkeypatch):
    from app.contacts import leads as L
    from app.models.campaign import Campaign
    from app.models.creator import Creator
    from app.models.deal import CreatorDeal

    asked = []

    async def fake_find_many(items, *, judge, count_shared=None):
        asked.extend(k for k, _ in items)
        return {k: {"email": {"UC1": "collabs@priyabuilds.com", "UC3": "new@lead.io"}[k], "email_source": "link_page",
                    "first_name": "Priya" if k == "UC1" else None, "socials": {"instagram": "https://instagram.com/priya"},
                    "searched_at": datetime.now(timezone.utc).isoformat()} for k, _ in items}

    monkeypatch.setattr(L, "find_many", fake_find_many)
    async with sf() as db:
        camp = await db.get(Campaign, "c1")
        out = await L.find_for_leads(db, camp, ["UC1", "UC2", "UC3", "nope"], user_id="u1", session_factory=sf)
        await db.commit()
    assert sorted(asked) == ["UC1", "UC3"]  # Sam was searched 3 days ago: reused
    assert out["UC2"]["email"] == "sam@codes.dev"
    async with sf() as db:
        camp = await db.get(Campaign, "c1")
        leads = {l["id"]: l for l in camp.campaign_leads}
        assert leads["UC1"]["socials"]["email"] == "collabs@priyabuilds.com"  # replaces the sponsor's copied address
        assert leads["UC1"]["socials"]["instagram"] == "https://instagram.com/priya" and leads["UC1"]["first_name"] == "Priya"
        assert leads["UC2"]["first_name"] == "Sam"
        d1, d3 = await db.get(CreatorDeal, "d1"), await db.get(CreatorDeal, "d3")
        assert d1.contact_email == "collabs@priyabuilds.com"
        assert d3.contact_email == "typed@founder.com"  # the founder's own edit is kept
        row = await db.get(Creator, "cr1")
        assert row.contacts["found"]["email"] == "collabs@priyabuilds.com" and row.contacts["emails"] == ["sponsor@acme.com"]


async def test_opted_out_addresses_and_recent_contacts(sf, monkeypatch):
    from app.contacts import leads as L
    from app.contacts.ledger import record_contact, suppress
    from app.models.campaign import Campaign

    async def fake_find_many(items, *, judge, count_shared=None):
        return {k: {"email": "collabs@priyabuilds.com", "searched_at": datetime.now(timezone.utc).isoformat()} for k, _ in items}

    monkeypatch.setattr(L, "find_many", fake_find_many)
    async with sf() as db:
        await record_contact(db, "u1", "Sam@Codes.dev", "other-campaign")
        await suppress(db, "collabs@priyabuilds.com", "opt_out")
        await db.commit()
    async with sf() as db:
        camp = await db.get(Campaign, "c1")
        out = await L.find_for_leads(db, camp, ["UC1", "UC2"], user_id="u1", session_factory=sf)
    assert out["UC1"]["email"] is None and out["UC1"]["suppressed"]
    assert out["UC2"]["contacted_before"]  # same founder, another campaign, 0 days ago


async def test_a_failing_search_changes_nothing(sf, monkeypatch):
    from app.contacts import leads as L
    from app.models.campaign import Campaign

    async def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(L, "find_many", boom)
    async with sf() as db:
        camp = await db.get(Campaign, "c1")
        assert await L.find_for_leads(db, camp, ["UC1"], user_id="u1", session_factory=sf) == {}
        assert camp.campaign_leads[0]["socials"]["email"] == "sponsor@acme.com"


async def test_gmail_never_sends_to_a_suppressed_address(sf):
    from fastapi import HTTPException

    from app.contacts.ledger import suppress
    from app.gmail.service import send_for_deal
    from app.models.deal import ConnectedAccount, CreatorDeal

    async with sf() as db:
        await suppress(db, "sponsor@acme.com", "bounce")
        d = await db.get(CreatorDeal, "d1")
        acct = ConnectedAccount(user_id="u1", email="me@x.com", refresh_token="x", status="active")
        with pytest.raises(HTTPException) as e:
            await send_for_deal(db, acct, d, "Hi", subject="Hello")
        assert e.value.status_code == 422
