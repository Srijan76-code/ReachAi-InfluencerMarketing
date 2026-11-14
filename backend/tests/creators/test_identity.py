"""One person, several accounts (roadmap F1.17b): the linking rules are code, and a name alone never merges."""

import pytest

from app.creators.identity import decide, links_of, own_keys, parse_link, similarity


@pytest.mark.parametrize("url,expected", [
    ("https://www.instagram.com/Sofia.Codes/", ("instagram", "sofia.codes")),
    ("https://instagram.com/p/C1abc/", None),
    ("https://x.com/SofiaCodes", ("x", "sofiacodes")),
    ("https://twitter.com/intent/tweet?text=hi", None),
    ("https://www.linkedin.com/in/sofia-codes-12ab/", ("linkedin", "sofia-codes-12ab")),
    ("https://www.youtube.com/@SofiaCodes", ("youtube", "@sofiacodes")),
    ("https://youtube.com/channel/UCabcdefghijklmnopqrstuv", ("youtube", "UCabcdefghijklmnopqrstuv")),
    ("https://notion.so/sofia", None),
    ("", None),
])
def test_parse_link(url, expected):
    assert parse_link(url) == expected


def yt(**kw):
    base = {"platform": "youtube", "platform_id": "UCsofia000000000000000000", "handle": "@SofiaCodes",
            "display_name": "Sofia Codes", "url": "https://www.youtube.com/@SofiaCodes", "cross_links": {}}
    base.update(kw)
    return base


def ig(**kw):
    base = {"platform": "instagram", "platform_id": "sofia.codes", "handle": "sofia.codes", "display_name": "Sofia ♡ | code",
            "url": "https://www.instagram.com/sofia.codes/", "cross_links": {}}
    base.update(kw)
    return base


def test_own_keys_cover_handles_ids_and_urls():
    assert ("youtube", "@sofiacodes") in own_keys(yt()) and ("youtube", "UCsofia000000000000000000") in own_keys(yt())
    assert ("instagram", "sofia.codes") in own_keys(ig())
    x = {"platform": "x", "platform_id": "123456", "handle": "SofiaCodes"}
    assert own_keys(x) == {("x", "sofiacodes")}  # numeric X ids are never in links


def test_links_ignore_the_accounts_own_platform():
    p = yt(cross_links={"youtube": "https://youtube.com/@SofiaCodes", "instagram": "https://instagram.com/sofia.codes"})
    assert links_of(p) == {"instagram": ("instagram", "sofia.codes")}


def test_links_both_ways_are_the_same_person():
    a = yt(cross_links={"instagram": "https://instagram.com/sofia.codes"})
    b = ig(display_name="Totally different name", cross_links={"youtube": "https://youtube.com/@SofiaCodes"})
    assert decide(a, b) == "link"


def test_one_way_link_with_a_matching_name_is_the_same_person():
    a = yt(cross_links={"instagram": "https://instagram.com/sofia.codes"})
    assert decide(a, ig()) == "link"


def test_one_way_link_to_someone_else_is_only_a_check():
    """A YouTube description linking a sponsor's or a friend's Instagram must never merge on its own."""
    a = yt(cross_links={"instagram": "https://instagram.com/notionhq"})
    sponsor = ig(platform_id="notionhq", handle="notionhq", display_name="Notion", url="https://instagram.com/notionhq")
    assert decide(a, sponsor) == "check"


def test_same_name_without_any_link_is_only_a_check():
    assert decide(yt(), ig()) == "check"


def test_unrelated_or_same_platform_never_link():
    other = ig(platform_id="cooking.mike", handle="cooking.mike", display_name="Mike Cooks", url="https://instagram.com/cooking.mike")
    assert decide(yt(), other) == "no"
    assert decide(yt(), yt(platform_id="UCother0000000000000000")) == "no"


def test_similarity_ignores_emoji_decorations_and_case():
    assert similarity({"display_name": "Sofia ♡ | Tech & AI"}, {"display_name": "SOFIA"}) == 1.0
    assert similarity({"display_name": "Sam"}, {"display_name": "Sam"}) == 0  # too short and common to trust
    assert similarity({"handle": "sofia.codes"}, {"handle": "SofiaCodes"}) == 1.0
    assert similarity({"display_name": "Ben Holmes (Dev)"}, {"handle": "benholmes"}) == 1.0
    assert similarity({"handle": "mike"}, {"handle": "mikey_cooks_daily"}) < 0.85
