"""Time-based "Needs you" suggestions (spec §7.8): follow-ups, late posts, live, paid. Replies and prices are
the negotiation agent's (tests/negotiation)."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.agent.proposals import Ev, money_in, propose

NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
TODAY = NOW.date()


def deal(**kw):
    base = dict(stage="contacted", fair_low=150, fair_high=210, typical_views=28300, quoted_rate=None, agreed_rate=None,
                deliverable="integration", usage_rights="none", exclusivity_days=0, post_by=None, post_url=None,
                paid_at=None, created_at=NOW - timedelta(days=1), creator_name="Priya Sharma")
    base.update(kw)
    return SimpleNamespace(**base)


def ev(i, type, days_ago, **payload):
    return Ev(str(i), type, payload, NOW - timedelta(days=days_ago))


def run(d, events=(), goal=None):
    return propose(d, list(events), name="Priya Sharma", goal=goal, today=TODAY, now=NOW)


def reply(i, days_ago, **signals):
    amounts = signals.pop("amounts", [])
    return ev(i, "creator_reply", days_ago, text="…", signals=signals, amounts=amounts)


def test_money_in_reads_common_ways_of_writing_prices():
    assert money_in("My rate is $1,200 for a segment") == [1200]
    assert money_in("$1.5k, or 900 USD for a short") == [1500, 900]
    assert money_in("I get 40k views and charge 2 dollars per… no") == [2]
    assert money_in("no price here, 30% off") == []


def test_nothing_to_do_right_after_contact():
    assert run(deal()) == []


def test_follow_ups_after_silence_then_stop():
    d = deal(created_at=NOW - timedelta(days=5))
    [p] = run(d)
    assert p.kind == "follow_up" and "Priya" in p.payload["message"] and p.key == "follow_up:0"
    sent = [ev(1, "message_sent", 5, kind="follow_up")]
    assert run(d, sent)[0].key == "follow_up:1"  # 5 days since the first follow-up
    sent.append(ev(2, "message_sent", 4, kind="follow_up"))
    assert run(d, sent) == []  # two follow-ups is the limit


def test_late_post_is_chased_and_live_link_moves_it():
    d = deal(stage="agreed", agreed_rate=200, post_by=TODAY - timedelta(days=2))
    [p] = run(d)
    assert p.kind == "chase_post" and "2 days ago" in p.reason
    assert run(d, [ev(1, "message_sent", 1, kind="chase_post")]) == []  # asked yesterday: wait
    assert run(d, [ev(1, "message_sent", 3, kind="chase_post")])[0].key.endswith(":1")
    [live] = run(deal(stage="content", post_url="https://youtube.com/watch?v=1"))
    assert live.kind == "mark_live"
    [pay] = run(deal(stage="live", agreed_rate=200))
    assert pay.kind == "mark_paid" and "$200" in pay.title
    assert run(deal(stage="paid", agreed_rate=200, paid_at=NOW)) == []
