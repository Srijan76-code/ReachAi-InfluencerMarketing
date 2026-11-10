"""Fair price for a deal (spec §8.7), and the greeting rule."""

import pytest

from app.deals import negotiation as N

FAIR = dict(fair_low=150.0, fair_high=210.0, typical_views=28_300)


def test_verdicts_against_the_fair_range():
    assert N.advise(**FAIR, quote=None).verdict is None
    assert N.advise(**FAIR, quote=120).verdict == "great"
    a = N.advise(**FAIR, quote=200)
    assert a.verdict == "accept" and (a.fair_low, a.fair_high) == (150, 210)
    c = N.advise(**FAIR, quote=300)
    assert c.verdict == "counter" and c.counter == 180 and "43% above" in c.reason and "28.3k views" in c.reason
    w = N.advise(**FAIR, quote=500)
    assert w.verdict == "walk_away" and w.counter == 210
    assert N.advise(fair_low=None, fair_high=None, typical_views=None, quote=100).verdict is None


def test_format_usage_and_exclusivity_change_the_fair_price():
    plain = N.advise(**FAIR, quote=300)
    rich = N.advise(**FAIR, quote=300, deliverable="dedicated", usage_rights="paid_90", exclusivity_days=30)
    assert rich.fair_high > plain.fair_high and rich.verdict in ("accept", "great")  # 210×1.6×1.7 ≈ 575
    assert N.advise(**FAIR, quote=300, deliverable="short").verdict == "walk_away"  # a short is worth half
    assert N.deal_multiplier("integration", "none", 0) == 1.0
    assert N.exclusivity_uplift(0) == 0 and N.exclusivity_uplift(45) == 0.2 and N.exclusivity_uplift(400) == 0.5


def test_greeting_uses_a_first_name_only_when_the_channel_looks_like_a_person():
    assert N.greeting_name("Krish Naik") == "Krish" and N.greeting_name("Priya") == "Priya"
    for channel in ("The CRM Guy", "Sales Systems India", "Data with Priya", "Analytics Simplified", "TechWithTim",
                    "MKBHD", "Ali Abdaal Podcast", "", None, "A B"):
        assert N.greeting_name(channel) == "there", channel


def test_small_prices_round_to_the_dollar_not_to_five():
    a = N.advise(fair_low=5.57, fair_high=9.66, typical_views=1350, quote=None)
    assert (a.fair_low, a.fair_high) == (6, 10)  # was $10–$10


