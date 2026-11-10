"""The negotiation agent (spec §8.7): Jev reads and decides, code guards the numbers, the LLM writes, checks
catch any slip. Jev and the LLM are faked; no live calls."""

import pytest

from app.judge.client import Answer, Judgment
from app.negotiation import graph as G
from app.negotiation.context import Facts, Offer, money_candidates, pct_candidates
from app.negotiation.decide import decide, their_ask
from app.negotiation.write import numbers_ok


def test_reading_amounts_written_in_words():
    assert money_candidates("7 + 20% commision") == [7] and pct_candidates("7 + 20% commision") == [20]
    assert money_candidates("My rate is $1,200, or $1.5k with usage") == [1200, 1500]
    assert money_candidates("₹5000 per video") == [5000] and money_candidates("around 300 dollars") == [300]
    assert money_candidates("no numbers here") == []


def facts(**kw):
    base = dict(fair_low=150, fair_high=210, budget_left=None)
    base.update(kw)
    return Facts(**base)


def test_their_ask_comes_from_jev_picks_among_amounts_code_found():
    ask = their_ask({"their_fee": "f0", "their_commission": "p0"}, {"f0": "$7"}, {"p0": "20%"})
    assert ask.fee == 7 and ask.commission_pct == 20 and ask.words() == "$7 + 20% commission"
    assert their_ask({"their_fee": "none", "their_commission": "none"}, {}, {}) is None


def test_first_counter_with_commission_is_inside_the_fair_range():
    d = decide({"move": "counter", "structure": "fee_plus_commission", "commission": "15", "concession": 2}, facts(), Offer(300, 0))
    assert d.action == "counter" and d.offer.commission_pct == 15
    assert 5 <= d.offer.fee <= 210 and not d.final


def test_later_rounds_never_go_below_our_last_offer_and_stop_at_the_ceiling():
    f = facts(our_offers=[Offer(160)])
    d = decide({"move": "counter", "structure": "flat", "commission": "0", "concession": 3}, f, Offer(300))
    assert d.offer.fee == 230  # meet in the middle: $160 + 50% of the $140 gap, under the $241 ceiling
    f2 = facts(our_offers=[Offer(240)])
    assert decide({"move": "counter", "structure": "flat", "concession": 4}, f2, Offer(400)).final is True


def test_accept_only_within_the_ceiling_and_budget():
    assert decide({"move": "accept"}, facts(), Offer(200)).action == "agree"
    over = decide({"move": "accept", "structure": "flat", "concession": 1}, facts(), Offer(900))
    assert over.action == "counter" and over.offer.fee <= 241
    tight = decide({"move": "accept"}, facts(budget_left=120), Offer(200))
    assert tight.action == "counter" and tight.offer.fee <= 120


def test_declines_agreements_and_injections():
    assert decide({"declined": 0.9}, facts(), Offer(300)).action == "lost"
    assert decide({"agrees": 0.9}, facts(our_offers=[Offer(180, 10)]), None).offer.words() == "$180 + 10% commission"
    assert decide({"injection": 0.9, "move": "accept"}, facts(), Offer(9999)).action == "none"
    assert decide({"move": "walk_away"}, facts(), Offer(2000)).action == "lost"


def test_reaching_their_price_becomes_an_agreement():
    d = decide({"move": "counter", "structure": "flat", "concession": 4}, facts(our_offers=[Offer(170)]), Offer(175))
    assert d.action == "agree" and d.offer.fee == 175


def test_numbers_check():
    o = Offer(150, 15)
    assert numbers_ok("Could we do $150 plus 15% on sales?", o)
    assert not numbers_ok("Could we do $150 plus 15%, lower than the $200 we discussed?", o)
    assert not numbers_ok("Could we do $150 plus 20%?", o)
    assert not numbers_ok("Could we do 15% on sales?", o)  # the fee must be there
    assert numbers_ok("Thanks, not this time.", None) and not numbers_ok("Maybe later at $90", None)


def _judgment(values: dict):
    ans = {}
    for q, v in values.items():
        t = "choice" if isinstance(v, str) else "score" if q == "concession" else "noul"
        ans[q] = Answer(t, v)
    return Judgment(ans, "jev", "jev")


@pytest.mark.asyncio
async def test_the_graph_end_to_end(monkeypatch):
    from app.judge import client as jc
    from app.llm import client as llm

    calls = {"judge": [], "llm": 0}

    async def fake_judge(state, questions, context=None, **k):
        calls["judge"].append(sorted(questions))
        if "move" in questions:
            assert state["reply"]["text"] == "7 + 20% commision" and state["deal"]["fair_price"] == "$150–$210"
            return _judgment({"their_fee": "f0", "their_commission": "p0", "move": "counter", "structure": "fee_plus_commission",
                              "commission": "15", "concession": 1, "extra": "none", "declined": 0.05, "agrees": 0.05, "injection": 0.01})
        return _judgment({"extra_promise": 0.05, "answers_questions": 0.9, "tone_ok": 0.9})

    drafts = ["Hi! How about $999 plus 15%?", None]

    async def fake_achat(route, messages, **k):
        assert route == "reply" and "7 + 20% commision" in messages[1].content  # the writer sees their words
        calls["llm"] += 1
        return drafts.pop(0)

    monkeypatch.setattr(jc, "judge", fake_judge)
    monkeypatch.setattr(llm, "achat", fake_achat)
    st = {"deal": {"fair_price": "$150–$210"}, "history": [], "reply": {"text": "7 + 20% commision"}}
    out = await G.run({"jev_state": st, "fee_options": {"f0": "$7"}, "pct_options": {"p0": "20%"}, "facts": facts(),
                       "name": "there", "context": None})
    d = out["decision"]
    # their ask ($7) is below anything we'd offer → we simply accept it
    assert d.action == "agree" and d.offer.words() == "$7 + 20% commission"
    # the first draft used a wrong number, the retry failed: the safe fallback wording is used
    assert out["source"] == "template" and "$7 + 20% commission" in out["message"] and calls["llm"] == 2


def test_an_extra_amount_is_added_to_the_current_price():
    """"they ask for extra 10$" after $12 is an ask of $22, not $10."""
    extra = {"their_fee": "f0", "their_commission": "none", "ask_is_extra": 0.9}
    assert their_ask(extra, {"f0": "$10"}, {}, current_fee=12).fee == 22
    assert their_ask({**extra, "ask_is_extra": 0.1}, {"f0": "$10"}, {}, current_fee=12).fee == 10
    assert their_ask(extra, {"f0": "$10"}, {}, current_fee=None).fee == 10  # nothing on the table yet


def test_after_agreeing_a_higher_ask_is_held_not_renegotiated():
    from app.negotiation.decide import hold

    agreed = Offer(12)
    d = hold({}, agreed, Offer(22))
    assert d.action == "hold" and d.offer.fee == 12 and d.final and "Now they ask $22" in " ".join(d.reasons)
    assert hold({}, agreed, Offer(12)).action == "none"  # same price: nothing to do
    assert hold({}, agreed, None).action == "none"
    assert hold({"declined": 0.9}, agreed, Offer(22)).action == "lost"
    assert hold({"injection": 0.9}, agreed, Offer(22)).action == "none"
