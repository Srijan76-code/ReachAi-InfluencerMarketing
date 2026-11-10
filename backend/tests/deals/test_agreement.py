"""Agreeing a deal: posts in words, the confirmation message, codes and links (all code, no model)."""

from datetime import date

import pytest
from fastapi import HTTPException

from app.deals import agreement as AG
from app.models.deal import CreatorDeal
from app.outreach.drafts import auto_channel, pick_text, texts_from_bundle


def test_posts_are_grouped_by_kind_and_date():
    posts = [("integration", date(2026, 11, 20)), ("short", date(2026, 11, 25)), ("short", date(2026, 11, 25))]
    assert AG.posts_words(posts) == ["1 sponsored segment by Nov 20", "2 shorts by Nov 25"]
    assert AG.posts_words([("dedicated", None)]) == ["1 dedicated video"]


def test_confirmation_lists_terms_link_and_code():
    t = AG.confirmation("Srijan", "$12", [("integration", date(2026, 11, 20))], "on_live", "https://app/r/abc", "SRIJAN10")
    assert t.startswith("Hi Srijan,") and "- 1 sponsored segment by Nov 20" in t and "- $12, paid when the post is live" in t
    assert "this link: https://app/r/abc and this code for your audience: SRIJAN10." in t
    assert "link" not in AG.confirmation("there", "$5", [("short", None)], None, None, None).split("agreed")[1].split("Send over")[0]


def test_codes_are_from_the_name_and_unique():
    code = AG.code_for("Srijan Patel", set())
    assert code.startswith("SRIJAN") and len(code) == 8 and code[-2:].isdigit()
    assert AG.code_for("123", set()).startswith("CREATOR")
    taken = {f"ASHA{i:02d}" for i in range(100) if i != 42}
    assert AG.code_for("Asha", taken) not in taken


def test_site_addresses_are_cleaned():
    assert AG.clean_url("acme.com/pricing") == "https://acme.com/pricing"
    assert AG.clean_url("http://acme.com") == "https://acme.com"
    assert AG.clean_url("") is None
    for bad in ("javascript:alert(1)", "localhost", "https://"):
        with pytest.raises(HTTPException):
            AG.clean_url(bad)


def test_first_message_per_channel():
    texts = texts_from_bundle({"email": {"subject": "Your M4 review", "body": "Hi email"}, "instagram": {"body": "Hi ig"}, "twitter": None})
    assert texts == {"email": {"subject": "Your M4 review", "body": "Hi email"}, "instagram": {"body": "Hi ig"}}
    assert pick_text(texts, "whatsapp") == {"body": "Hi ig"} and pick_text(texts, "email")["subject"] == "Your M4 review"
    assert auto_channel(CreatorDeal(contact_email="a@b.co"), {}) == "email"
    assert auto_channel(CreatorDeal(), {"socials": {"twitter": "x.com/a"}}) == "twitter"
    assert auto_channel(CreatorDeal(channel="whatsapp", contact_email="a@b.co"), {}) == "whatsapp"
