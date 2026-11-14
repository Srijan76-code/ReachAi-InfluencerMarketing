"""Finding a creator's email and first name from free sources (spec §7.1, roadmap F6.1). Pages, DNS and Jev
are simulated: no live calls."""

import json

import httpx
import pytest

from app.contacts import fetch as F
from app.contacts.extract import clean_email, emails_in
from app.contacts.find import find_contact
from app.judge.client import Answer, Judgment

pytestmark = pytest.mark.asyncio

LINK_PAGE = """<html><a href="https://www.instagram.com/priya.builds">IG</a>
<a href="mailto:collabs@priyabuilds.com?subject=hi">Email me</a>
<a href="https://priyabuilds.com">My site</a><p>support@linktr.ee</p></html>"""
SITE_HOME = """<html><a href="/work-with-me">Work with me</a><p>Designed by studio@webflowpros.io</p></html>"""
SITE_CONTACT = """<html><p>Brands: hello [at] priyabuilds [dot] com</p>
<a href="/cdn-cgi/l/email-protection" data-cfemail="5a2a2833233b1a382f2933343f292974393537">x</a></html>"""


def pages(extra=None, dead_domains=()):
    """A fake internet: link page, website, DNS-over-HTTPS. Records what was fetched."""
    fetched = []
    routes = {
        "https://linktr.ee/priya": LINK_PAGE,
        "https://priyabuilds.com": SITE_HOME,
        "https://priyabuilds.com/work-with-me": SITE_CONTACT,
        **(extra or {}),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url).rstrip("/")
        if request.url.host in ("cloudflare-dns.com", "dns.google"):
            name = request.url.params["name"]
            if name in dead_domains:
                return httpx.Response(200, json={"Status": 3})
            return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 15 if request.url.params["type"] == "MX" else 1}]})
        fetched.append(url)
        if url in routes:
            body = routes[url]
            if isinstance(body, httpx.Response):
                return body
            return httpx.Response(200, text=body, headers={"content-type": "text/html"})
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), fetched


@pytest.fixture(autouse=True)
def public_hosts(monkeypatch):
    async def public(host):
        return not host.startswith(("127.", "10.", "169.254.", "192.168.")) and host != "localhost"
    monkeypatch.setattr(F, "_public", public)


PRIYA = {"creator_id": "c1", "platform": "youtube", "display_name": "Priya Builds", "handle": "@priyabuilds",
         "bio": "Building apps every week. This video is not sponsored. I'm Priya!",
         "external_links": ["https://linktr.ee/priya"], "contacts": {"emails": []},
         "recent_posts": [{"text": "My setup", "description": "This video is sponsored by Acme. partners@acme.com"}]}


def jev(email_pick=None, name_pick=None, conf=0.92, injection=0.0, seen=None):
    async def judge(state, questions):
        if seen is not None:
            seen.append((state, questions))
        answers = {"injection": Answer("noul", injection)}
        if "email" in questions:
            crit = questions["email"].criteria
            key = next((k for k, v in crit.items() if v == email_pick), "none_of_these")
            answers["email"] = Answer("choice", key, conf)
        if "first_name" in questions:
            crit = questions["first_name"].criteria
            key = next((k for k, v in crit.items() if v == name_pick), "not_stated")
            answers["first_name"] = Answer("choice", key, conf)
        return Judgment(answers=answers, model="sim", source="jev")
    return judge


async def test_extracts_every_way_an_address_is_written():
    page = SITE_CONTACT + '<a href="mailto:Me@Site.io">m</a> icon@2x.png noreply@site.io you@example.com'
    got = emails_in(page)
    assert "hello@priyabuilds.com" in got and "me@site.io" in got
    assert "priya@business.com" in got  # Cloudflare-protected address, decoded
    assert not any(e.startswith(("noreply", "you@")) or e.endswith(".png") for e in got)
    assert clean_email("mailto:Collabs@X.com.") == "collabs@x.com"


async def test_finds_the_link_page_address_and_checks_it_with_jev():
    client, fetched = pages()
    seen = []
    out = await find_contact([PRIYA], judge=jev("collabs@priyabuilds.com", "Priya", seen=seen), client=client)
    assert out["email"] == "collabs@priyabuilds.com" and out["email_source"] == "link_page"
    assert out["email_checked"] == "jev" and out["first_name"] == "Priya"
    assert out["socials"]["instagram"] == "https://www.instagram.com/priya.builds"
    offered = set(seen[0][1]["email"].criteria.values())
    # the sponsor's address, the link service's own inbox: never offered
    assert "partners@acme.com" not in offered and "support@linktr.ee" not in offered
    assert {"hello@priyabuilds.com", "collabs@priyabuilds.com"} <= offered
    # the bio ("Hi, I'm Priya") and the channel name both give "Priya": offered once
    assert list(seen[0][1]["first_name"].criteria.values()).count("Priya") == 1
    assert "https://priyabuilds.com/work-with-me" in fetched  # followed the contact link on the site
    await client.aclose()


async def test_unsure_jev_means_no_email():
    client, _ = pages()
    out = await find_contact([PRIYA], judge=jev("collabs@priyabuilds.com", conf=0.6), client=client)
    assert out["email"] is None and out["candidates"] >= 2
    client, _ = pages()
    out = await find_contact([PRIYA], judge=jev(None), client=client)  # none_of_these
    assert out["email"] is None
    await client.aclose()


async def test_without_jev_only_the_creators_own_words_count():
    async def down(state, questions):
        raise RuntimeError("Jev down")

    client, _ = pages()
    out = await find_contact([PRIYA], judge=down, client=client)
    assert out["email"] == "collabs@priyabuilds.com" and out["email_checked"] == "rule"  # link page: ok
    site_only = {**PRIYA, "external_links": ["https://priyabuilds.com"]}
    client, _ = pages()
    out = await find_contact([site_only], judge=down, client=client)
    assert out["email"] is None  # a website address needs Jev's check
    assert out["first_name"] == "Priya"  # "Priya Builds" reads as a name: the code rule's greeting


async def test_injection_in_the_bio_ignores_jevs_answer():
    client, _ = pages()
    out = await find_contact([PRIYA], judge=jev("hello@priyabuilds.com", injection=0.95), client=client)
    assert out["email_checked"] == "rule" and out["email"] == "collabs@priyabuilds.com"


async def test_dead_domains_and_shared_inboxes():
    bio_only = {**PRIYA, "external_links": [], "bio": "Business: deals@gone-domain.xyz or team@bigagency.com"}
    client, _ = pages(dead_domains={"gone-domain.xyz"})

    async def shared(email, own):
        return 7 if email == "team@bigagency.com" else 0

    seen = []
    out = await find_contact([bio_only], judge=jev("team@bigagency.com", seen=seen), count_shared=shared, client=client)
    offered = seen[0][0]["candidates"]
    assert [c["address"] for c in offered] == ["team@bigagency.com"]  # the dead domain is gone
    assert offered[0]["listed_by_other_people"] == 7  # Jev sees that it's shared (an agency)
    assert out["email"] == "team@bigagency.com"

    async def down(state, questions):
        raise RuntimeError("down")

    client, _ = pages()
    out = await find_contact([{**bio_only, "bio": "team@bigagency.com"}], judge=down, count_shared=shared, client=client)
    assert out["email"] is None  # without Jev, a shared inbox isn't used


async def test_every_account_of_the_person_counts():
    x = {"creator_id": "c2", "platform": "x", "display_name": "Priya", "bio": "DMs open. biz: priya@hey.com",
         "external_links": []}
    client, _ = pages()
    seen = []
    await find_contact([{**PRIYA, "external_links": []}, x], judge=jev("priya@hey.com", seen=seen), client=client)
    assert "priya@hey.com" in seen[0][1]["email"].criteria.values()
    assert len(seen[0][0]["creator"]["accounts"]) == 2


async def test_untrusted_urls_never_reach_private_addresses(monkeypatch):
    monkeypatch.undo()  # the real check
    redirect = httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})
    client, fetched = pages(extra={"https://evil.example.org": redirect})
    for url in ("http://127.0.0.1:8000/admin", "http://169.254.169.254/latest", "http://10.0.0.5", "file:///etc/passwd",
                "http://localhost/x"):
        assert await F.fetch_page(client, url) is None
    assert fetched == []
    assert await F._public("8.8.8.8") and not await F._public("192.168.1.1")

    async def public(host):
        return host == "evil.example.org"
    monkeypatch.setattr(F, "_public", public)
    assert await F.fetch_page(client, "https://evil.example.org") is None  # redirect to metadata: refused
    assert fetched == ["https://evil.example.org"]


async def test_big_pages_are_cut_and_non_html_skipped():
    big = "<p>a</p>" * 200_000 + "late@far.com"
    client, _ = pages(extra={"https://big.site": big,
                             "https://img.site": httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})})
    got = await F.fetch_page(client, "https://big.site")
    assert got and len(got[1]) <= 600_000 and "late@far.com" not in got[1]
    assert await F.fetch_page(client, "https://img.site") is None
    json.dumps(got[0])
