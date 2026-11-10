"""Add a creator by their channel link (F1.23): measured like a search, no Jev or LLM."""

import pytest

from app.creators.by_link import lead_from_link, parse_youtube
from tests.platforms.youtube_replay import ReplayAPI


def test_parse_links():
    cid = "UCS2BQtyF7TwP0DImVM0H4Uw"
    assert parse_youtube(f"https://www.youtube.com/channel/{cid}") == (cid, None)
    assert parse_youtube(f"https://youtube.com/channel/{cid}/videos?x=1") == (cid, None)
    assert parse_youtube(cid) == (cid, None)
    assert parse_youtube("https://www.youtube.com/@krishnaik06") == (None, "krishnaik06")
    assert parse_youtube("@some.creator") == (None, "some.creator")
    assert parse_youtube("https://instagram.com/x") == (None, None)


@pytest.mark.asyncio
async def test_lead_from_a_recorded_channel():
    api = ReplayAPI()
    cid = next(iter(api.items["channels"]))
    lead = await lead_from_link(f"https://www.youtube.com/channel/{cid}", {"campaign": {"industry": "saas"}}, api=api,
                                email="creator@x.io", topics=["python"])
    assert lead["id"] == cid and lead["added_by_you"] is True and lead["deal_status"] == "Added by you"
    assert lead["socials"]["email"] == "creator@x.io" and lead["found_via"] == "added_by_you"
    assert lead["metrics"]["avg_views"] >= 0 and "fair_high" in lead
    assert await lead_from_link("https://www.youtube.com/channel/UC0000000000000000000000", {}, api=api) is None
