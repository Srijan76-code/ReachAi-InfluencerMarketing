"""The negotiation agent as a LangGraph graph (spec §8.7, roadmap F7.9):

    judge (Jev reads their reply and decides the move) → guard (code: exact terms within limits)
      → write (LLM) → check (code: numbers; Jev: no extra promises) → [write again once] → done

Runs whenever a creator's reply arrives (Gmail sync, or the founder pastes or types it). The result becomes a
suggestion in To do; nothing is sent until the founder approves it. Short-lived, so no checkpointer."""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.billing.costs import CostContext
from app.judge import constants as K
from app.negotiation import write as W
from app.negotiation.context import Facts
from app.negotiation.decide import Decision, decide, hold, their_ask


class NegState(TypedDict, total=False):
    jev_state: dict
    fee_options: dict
    pct_options: dict
    facts: Facts
    name: str
    context: CostContext
    current_fee: Optional[float]  # the price on the table (agreed, else our last offer): for "$10 more"
    agreed: Any  # Offer: the agreed terms, when the deal is already agreed (then the agent only holds or flags)
    answers: dict
    ask: Any
    decision: Decision
    message: Optional[str]
    source: str
    feedback: Optional[str]
    attempts: int
    check: dict


async def judge_node(s: NegState) -> NegState:
    from app.judge.client import judge
    from app.judge.questions import negotiation_questions

    j = await judge(s["jev_state"], negotiation_questions(s["fee_options"], s["pct_options"]), context=s["context"])
    answers = {q: (j.noul(q) if a.type == "noul" else j.choice(q) if a.type == "choice" else j.score(q)) for q, a in j.answers.items()}
    return {"answers": answers, "ask": their_ask(answers, s["fee_options"], s["pct_options"], s.get("current_fee"))}


async def guard_node(s: NegState) -> NegState:
    if s.get("agreed") is not None:
        return {"decision": hold(s["answers"], s["agreed"], s["ask"]), "attempts": 0}
    return {"decision": decide(s["answers"], s["facts"], s["ask"]), "attempts": 0}


async def write_node(s: NegState) -> NegState:
    d = s["decision"]
    text = await W.draft(s["jev_state"], d.action, d.offer, d.structure, d.extra, d.final, s["name"], s["context"], s.get("feedback"))
    return {"message": text, "attempts": s.get("attempts", 0) + 1}


async def check_node(s: NegState) -> NegState:
    from app.judge.client import judge
    from app.judge.questions import draft_check_questions

    d, text = s["decision"], s.get("message")
    if not text:
        return {"check": {"ok": False, "why": "the AI was unavailable"}}
    if not W.numbers_ok(text, d.offer if d.action != "lost" else None):
        return {"check": {"ok": False, "why": "it used a price or percentage other than the decided terms"}}
    j = await judge({"draft": text, "terms": d.offer.words() if d.offer else "no new terms", "reply": s["jev_state"]["reply"]},
                    draft_check_questions(), context=s["context"])
    if j.noul("extra_promise") > K.DRAFT_EXTRA_PROMISE_ABOVE:
        return {"check": {"ok": False, "why": "it promised something that wasn't decided"}}
    return {"check": {"ok": True, "tone": j.noul("tone_ok"), "answers": j.noul("answers_questions")}}


def _after_guard(s: NegState) -> str:
    return "write" if s["decision"].action in ("counter", "agree", "lost", "hold") else END


def _after_check(s: NegState) -> str:
    if s["check"].get("ok"):
        return "done"
    return "retry" if s.get("attempts", 0) < 2 and s.get("message") else "fallback"


async def retry_node(s: NegState) -> NegState:
    return {"feedback": s["check"]["why"]}


async def done_node(s: NegState) -> NegState:
    return {"source": "ai"}


async def fallback_node(s: NegState) -> NegState:
    d = s["decision"]
    return {"message": W.fallback(s["name"], d.action, d.offer, d.final), "source": "template"}


def build():
    g = StateGraph(NegState)
    for name, fn in (("judge", judge_node), ("guard", guard_node), ("write", write_node), ("check", check_node),
                     ("retry", retry_node), ("done", done_node), ("fallback", fallback_node)):
        g.add_node(name, fn)
    g.set_entry_point("judge")
    g.add_edge("judge", "guard")
    g.add_conditional_edges("guard", _after_guard, {"write": "write", END: END})
    g.add_edge("write", "check")
    g.add_conditional_edges("check", _after_check, {"done": "done", "retry": "retry", "fallback": "fallback"})
    g.add_edge("retry", "write")
    g.add_edge("done", END)
    g.add_edge("fallback", END)
    return g.compile()


_GRAPH = None


async def run(state: NegState) -> NegState:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build()
    return await _GRAPH.ainvoke(state)
