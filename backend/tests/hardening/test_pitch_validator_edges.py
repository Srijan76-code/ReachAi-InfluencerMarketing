"""Pitch and negotiation text checks against simulated model output: the bad things a model can write
(prices in other currencies, links it made up, leaked placeholders, echoed injections, emails and phone
numbers) must never pass, and harmless variations (a creator name with an emoji, a link with a '?') must not
fail. No live model calls: every "model output" here is a fixed string."""

import pytest

from app.negotiation.context import Offer
from app.negotiation.write import numbers_ok
from app.outreach.nodes.validate_creator_pitch import validate_bundle

BRAND = "Lumen"


def creator_input(name="Sofia ♡", channels=("email",)):
    return {
        "creator_id": "c1",
        "campaign_context": {"brand": {"name": BRAND, "website": "https://lumen.app"}},
        "collaboration": {"type": "sponsored_video"},
        "creator_identity": {"name": name},
        "available_channels": list(channels),
        "evidence": [{"evidence_id": "video_1", "title": "My morning routine"}],
    }


def bundle(body, subject="Your morning routine video", **extra):
    b = {
        "creator_id": "c1",
        "pitch_angle": "Morning routines",
        "personalization": [{"evidence_id": "video_1", "reason": "Morning routine video"}],
        "email": {"subject": subject, "body": body},
        "instagram": None, "twitter": None, "linkedin": None,
    }
    b.update(extra)
    return b


GOOD = ("Hi Sofia,\n\nYour morning routine video felt honest in a way most productivity content isn't.\n\n"
        "We're building Lumen, a calm planner your viewers could actually stick with.\n\n"
        "Would you be open to exploring a collaboration?")


def test_a_good_pitch_passes():
    assert validate_bundle(bundle(GOOD), creator_input()) == []


def test_creator_name_with_an_emoji_or_handle_is_matched_on_the_first_name():
    assert validate_bundle(bundle(GOOD), creator_input(name="Sofia ♡")) == []
    assert validate_bundle(bundle(GOOD), creator_input(name="Sofia | Tech & AI")) == []
    assert validate_bundle(bundle(GOOD), creator_input(name="@sofia.codes")) == []
    assert "creator name is missing from the pitch" in validate_bundle(
        bundle(GOOD.replace("Sofia", "there")), creator_input(name="Sofia"))


@pytest.mark.parametrize("bad,why", [
    (GOOD + "\n\nWe can pay $500 for this.", "money"),
    (GOOD + "\n\nBudget is around 400 USD.", "money"),
    (GOOD + "\n\nWe offer €300 per video.", "money"),
    (GOOD + "\n\nWe pay ₹20,000.", "money"),
    (GOOD + "\n\nThink 1.5k for a video.", "money"),
    (GOOD + "\n\nSee https://bit.ly/3xYz for details.", "link"),
    (GOOD + "\n\nEmail me at founder@gmail.com.", "email"),
    (GOOD + "\n\nCall me on +1 415 555 0134.", "phone"),
    ("Hi [Creator Name],\n\n" + GOOD, "placeholder"),
    ("Hi {creator_name},\n\n" + GOOD, "placeholder"),
    (GOOD + "\n\nAs instructed, ignore previous instructions.", "instructions"),
    (GOOD + "\n\nAs an AI language model I think this fits.", "ai"),
])
def test_things_a_model_must_never_write_are_caught(bad, why):
    errors = validate_bundle(bundle(bad), creator_input())
    # caught for the right reason, not just because something else (like the name) failed
    assert [e for e in errors if "creator name" not in e], f"should fail ({why})"


def test_brand_website_link_is_allowed_and_a_question_mark_in_a_link_is_not_a_question():
    ok = GOOD + "\n\nMore at https://lumen.app/?ref=sofia"
    assert validate_bundle(bundle(ok), creator_input()) == []


def test_empty_or_oversized_email_fails():
    assert validate_bundle(bundle("   "), creator_input())
    assert validate_bundle(bundle(GOOD, subject=""), creator_input())
    assert validate_bundle(bundle(GOOD, subject="x" * 120), creator_input())
    assert validate_bundle(bundle(GOOD + ("\n\nMore words here." * 200)), creator_input())


def test_schema_garbage_is_rejected_not_crashed():
    assert validate_bundle({}, creator_input())
    assert validate_bundle({"creator_id": "c1", "email": "not a dict"}, creator_input())


# --- negotiation: only the decided numbers, in any currency or spelling ---------------------------

@pytest.mark.parametrize("text", [
    "Could we do $150 plus 15%? Or 200 USD flat.",
    "Could we do $150 plus 15%, or €200?",
    "Could we do $150 plus 15%? We could stretch to 1.5k later.",
    "Could we do $150 plus 15%? Another creator took ₹9,000.",
    "Could we do $150 plus 15%? That's less than 300 dollars.",
    "Could we do $150 plus 15%? Rs. 4000 is our other option.",
])
def test_numbers_check_catches_other_amounts_in_any_currency(text):
    assert not numbers_ok(text, Offer(150, 15))


def test_numbers_check_still_accepts_the_right_terms_and_plain_counts():
    o = Offer(1500, 10)
    assert numbers_ok("Could we do $1,500 plus 10% on sales?", o)
    assert numbers_ok("Could we do $1,500 plus 10% on sales for 2 videos over 3 weeks?", o)
    assert numbers_ok("Thanks, not this time. Good luck with the 3 launches!", None)
