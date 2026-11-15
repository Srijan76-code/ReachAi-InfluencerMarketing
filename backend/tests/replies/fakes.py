"""Simulated Jev and reply writer for the reply agent: no live calls. The writer gets the real context the agent
built (as JSON in its prompt), so tests can check what it was shown and answer like a model would."""

from __future__ import annotations

import json

from app.judge.client import Answer, Judgment
from app.replies.writer import Draft

GOOD_RUBRIC = {"answers": 0.9, "promise": 0.05, "rude": 0.0, "template": 0.1, "ask_read": 0.95, "value": 0.9,
               "safe_to_send": 0.9}
SCORES = {"voice": 2, "fair": 2}


def jev(read: dict | None = None, rubric: dict | None = None, *, invented: float = 0.05):
    """`read`: Jev's reading of the creator's message; `rubric`: overrides for the draft check."""
    read = {"opt_out": 0.0, "injection": 0.0, "needs_founder": 0.0, "asks_question": 0.9, **(read or {})}
    rubric = {**GOOD_RUBRIC, **(rubric or {})}
    calls = []

    async def judge(state, questions, context=None, **k):
        calls.append((state, set(questions)))
        if "opt_out" in questions:
            return Judgment({q: Answer("noul", read[q]) for q in questions}, "jev", "jev")
        out = {}
        for q in questions:
            if q.startswith("unsupported_"):
                out[q] = Answer("noul", invented)
            elif q in SCORES:
                out[q] = Answer("score", rubric.get(q, SCORES[q]))
            else:
                out[q] = Answer("noul", rubric.get(q, 0.9))
        return Judgment(out, "jev", "jev")
    judge.calls = calls
    return judge


def context_of(messages) -> dict:
    return json.loads(messages[1].content.split("CONTEXT (JSON):\n", 1)[1])


def writer(answer):
    """`answer(ctx: dict, note: dict | None) -> dict` (Draft fields) or a fixed dict."""
    seen = []

    async def achat(route, messages, schema=None, **k):
        assert route == "reply" and schema is Draft
        ctx = context_of(messages)
        note = json.loads(messages[2].content.split("\n", 1)[1]) if len(messages) > 2 else None
        seen.append((ctx, note))
        return Draft(**(answer(ctx, note) if callable(answer) else answer))
    achat.seen = seen
    return achat


def install(monkeypatch, judge, achat):
    from app.judge import client as jc
    from app.llm import client as llm

    monkeypatch.setattr(jc, "judge", judge)
    monkeypatch.setattr(llm, "achat", achat)
