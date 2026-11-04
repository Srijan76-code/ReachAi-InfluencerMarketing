"""The "Needs you" suggestions (spec §7.8): one clear next step per deal, from code only."""

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


def test_quote_above_fair_suggests_a_counter_with_code_numbers():
    d = deal(stage="negotiating", quoted_rate=300)
    [p] = run(d, [ev(1, "quoted_rate", 0, to=300)])
    assert p.kind == "send_counter" and p.payload["amounts"] == {"counter": 180} and "$180" in p.payload["message"]
    # once sent, nothing more until they answer
    assert run(d, [ev(1, "quoted_rate", 1, to=300), ev(2, "message_sent", 0, kind="send_counter", amounts={"counter": 180})]) == []


def test_fair_quote_suggests_agreeing():
    [p] = run(deal(stage="negotiating", quoted_rate=200))
    assert p.kind == "agree" and p.payload["agreed_rate"] == 200 and p.payload["stage"] == "agreed"


def test_sales_goal_counters_with_fee_plus_commission():
    [p] = run(deal(quoted_rate=300), goal="sales")
    assert p.payload["angle"] == "performance" and p.payload["amounts"]["commission_pct"] == 10


def test_reply_with_one_price_is_written_down_first():
    [p] = run(deal(), [reply(1, 0, gives_price=0.9, amounts=[450])])
    assert p.kind == "record_quote" and p.payload == {"quoted_rate": 450}
    # two prices: we don't guess which one is theirs
    assert all(x.kind != "record_quote" for x in run(deal(), [reply(1, 0, gives_price=0.9, amounts=[450, 900])]))


def test_reply_accepting_our_offer_suggests_agreeing_at_what_we_offered():
    d = deal(stage="negotiating", quoted_rate=300)
    events = [ev(1, "quoted_rate", 3, to=300),
              ev(2, "message_sent", 2, kind="send_counter", amounts={"base": 130, "commission_pct": 10, "counter": 180}),
              reply(3, 0, agrees=0.95)]
    [p] = run(d, events)
    assert p.kind == "agree" and p.payload["agreed_rate"] == 130 and p.payload["deal_type"] == "base_plus_commission"


def test_edited_message_without_our_numbers_never_becomes_an_agreement():
    d = deal(stage="negotiating", quoted_rate=300)
    events = [ev(1, "quoted_rate", 3, to=300), ev(2, "message_sent", 2, kind="send_counter", amounts=None), reply(3, 0, agrees=0.95)]
    assert all(p.kind != "agree" or p.payload.get("message") for p in run(d, events))


def test_declined_and_ignored_replies():
    [p] = run(deal(quoted_rate=300), [reply(1, 0, declined=0.9)])
    assert p.kind == "mark_lost"
    # a reply that looked aimed at an AI is ignored: no suggestion comes from it
    assert all(p.kind != "mark_lost" for p in run(deal(quoted_rate=300), [reply(1, 0, ignored=True, declined=0.99)]))


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


def test_no_fair_price_means_no_counter():
    assert run(deal(fair_high=None, fair_low=None, quoted_rate=300)) == []


# --- negotiation memory -------------------------------------------------------------------------

def test_later_counters_move_toward_their_ask_and_end_with_a_final_offer():
    d = deal(stage="negotiating", quoted_rate=300)
    events = [ev(1, "quoted_rate", 5, to=300), ev(2, "message_sent", 4, kind="send_counter", amounts={"counter": 180}),
              ev(3, "quoted_rate", 1, to=260)]
    [p] = run(d.__class__(**{**vars(d), "quoted_rate": 260}), events)
    # $180 + 40% of the $80 gap = $212 → capped at the top of the fair range ($210): final offer
    assert p.kind == "send_counter" and p.payload["amounts"] == {"counter": 210} and p.payload["final"] is True
    assert p.title == "Final offer: $210" and "You offered $180, they ask $260" in p.reason
    assert "the most we can do" in p.payload["message"] and "$180" not in p.payload["message"]


def test_a_later_counter_moves_up_but_never_below_what_we_already_offered():
    d = deal(stage="negotiating", quoted_rate=1500, fair_low=300, fair_high=1000)
    events = [ev(1, "quoted_rate", 5, to=1500), ev(2, "message_sent", 4, kind="send_counter", amounts={"counter": 400}),
              ev(3, "quoted_rate", 1, to=1500)]
    [p] = run(d, events)
    assert p.payload["amounts"]["counter"] == 840 and p.payload["final"] is False  # 400 + 0.4 × 1,100
    assert p.payload["round"] == 2 and "move up to $840" in p.payload["message"]
    # they came down below what we offered? we never go lower than our own offer
    from app.deals import negotiation as N
    a = N.advise(fair_low=300, fair_high=1000, typical_views=1, quote=1500)
    assert N.next_offer(a, 350, N.History(offers=[400.0], asks=[])) == (400, False)


def test_still_too_high_after_our_final_offer_suggests_marking_lost():
    d = deal(stage="negotiating", quoted_rate=280)
    events = [ev(1, "quoted_rate", 5, to=300), ev(2, "message_sent", 4, kind="send_counter", amounts={"counter": 210}, final=True),
              ev(3, "quoted_rate", 1, to=280)]
    [p] = run(d, events)
    assert p.kind == "mark_lost" and "final offer of $210" in p.reason


def test_fee_plus_commission_offers_count_as_their_full_price_in_the_history():
    from app.agent.proposals import history
    h = history([ev(1, "message_sent", 2, amounts={"base": 50, "commission_pct": 10, "counter": 65}), ev(2, "quoted_rate", 1, to=77)])
    assert h.offers == [65.0] and h.asks == [77.0] and h.rounds == 1
