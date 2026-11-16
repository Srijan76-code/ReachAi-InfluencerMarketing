"""The reply agent (spec §8.6c, decided Nov 15): the AI writes the reply, Jev checks it, code enforces the limits.

    read (Jev: stop? instructions to an AI? something only the founder knows?)
      → checked writer: write (LLM, instructions.md) → hard limits (code) → rubric (Jev) → reviewer note → ≤2 rewrites
      → outcome (code): send | decide | ask_founder | wait | new_contact | opt_out | hold

What happens next is decided here in code from the draft's action and Jev's scores, never by the model alone:
- send: a reply or counter that passed every check and Jev says can go as is (autopilot may send it);
- decide: they accepted or declined: always the founder's call (Agree / Mark lost);
- ask_founder: they asked something our facts don't cover: the founder is asked, the answer is remembered;
- wait: out of office until a date; new_contact: someone else handles it (the founder confirms the address);
- opt_out: they asked us to stop; hold: anything else (failed checks, AI down): the founder reads it."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from app.agents.checked_writer import CheckedTask, Outcome, run
from app.billing.costs import CostContext
from app.replies import constants as R
from app.replies import judge as J
from app.replies import writer as W
from app.replies.context import ReplyContext
from app.replies.writer import Draft

logger = logging.getLogger(__name__)

MAX_WAIT_DAYS = 60  # "away until ..." further out than this is held for the founder


@dataclass
class ReplyResult:
    outcome: str  # send | decide | ask_founder | wait | new_contact | opt_out | hold | agent_task (the founder's agent writes it)
    draft: Optional[Draft] = None
    reason: str = ""
    questions: list[str] = field(default_factory=list)  # ask_founder: in plain words the founder can answer
    failed: list[str] = field(default_factory=list)  # rubric checks the last draft failed (held drafts)
    resume_on: Optional[date] = None
    rounds: int = 0
    signals: dict = field(default_factory=dict)  # Jev's reading of their message, and safe_to_send
    history: list = field(default_factory=list)


def _show(d: Draft) -> dict:
    return {"action": d.action, "message": d.message, "price": d.price.words() if d.price else None,
            "their_ask": d.their_ask.words() if d.their_ask else None, "missing_info": d.missing_info}


def _wait_until(d: Draft, today: date) -> Optional[date]:
    try:
        until = date.fromisoformat((d.resume_on or "")[:10])
    except ValueError:
        return None
    return until if today < until <= today + timedelta(days=MAX_WAIT_DAYS) else None


def outcome(ctx: ReplyContext, out: Outcome, signals: dict, *, today: date) -> ReplyResult:
    """What happens to the draft, decided in code."""
    base = dict(rounds=out.rounds, signals=signals, history=out.history)
    if out.source != "ai":
        last = out.history[-1] if out.history else {}
        failed = [c.get("check") for c in last.get("critical", [])]
        why = {"writer_down": "ReachAI couldn't write this reply right now. Read it yourself, or try again in a minute.",
               "checker_down": "ReachAI couldn't check this reply right now. Read it before sending."}.get(
            out.why or "", "The draft didn't pass the checks after two rewrites. Fix it and send it yourself.")
        return ReplyResult("hold", out.output, why, failed=failed, **base)
    d: Draft = out.output
    signals = {**signals, **(out.review.signals if out.review else {})}
    base["signals"] = signals
    if d.action == "wait":
        until = _wait_until(d, today)
        if until:
            return ReplyResult("wait", d, f"They're away. ReachAI writes again after {until:%-d %b}.", resume_on=until, **base)
        return ReplyResult("hold", d, "They mentioned being away, but no clear date. Read it yourself.", **base)
    if d.action == "new_contact" and d.new_contact_email:
        return ReplyResult("new_contact", d, f"They asked us to write to {d.new_contact_email} instead.", **base)
    if d.action == "ask_founder" or d.missing_info:
        qs = [q.strip() for q in d.missing_info if q and q.strip()][:5] or ["They asked something ReachAI doesn't know. What should we tell them?"]
        return ReplyResult("ask_founder", d, "They asked something only you can answer.", questions=qs, **base)
    if signals.get("needs_founder", 0) >= R.NEEDS_FOUNDER_FROM:
        return ReplyResult("ask_founder", d, "They asked something only you can answer.",
                           questions=["They asked something ReachAI doesn't know (see their message). What should we tell them?"], **base)
    if d.action in ("accept", "close"):
        return ReplyResult("decide", d, "They accepted." if d.action == "accept" else "They declined.", **base)
    if signals.get("safe_to_send", 0) >= R.SAFE_TO_SEND_MIN:
        return ReplyResult("send", d, d.strategy or "Passed every check.", **base)
    return ReplyResult("hold", d, "The reply passed the checks, but ReachAI isn't sure it can go as is. Check it first.", **base)


async def reply(ctx: ReplyContext, *, context: CostContext, judge=None, write=None, today: Optional[date] = None,
                read_only: bool = False) -> ReplyResult:
    """Runs the whole agent on one conversation. `judge(state, questions)` and `write(ctx, context, note)` default to
    Jev and the reply route (tests pass fakes). `read_only`: only Jev's reading of their message (opt-out, instructions
    to an AI), no writing: the founder's own agent writes the reply (outcome "agent_task")."""
    if judge is None:
        from app.judge.client import judge as jev

        async def judge(state, questions):
            return await jev(state, questions, context=context)
    write = write or W.write
    today = today or date.today()
    try:
        signals = await J.read(ctx, judge)
    except Exception as exc:  # noqa: BLE001 - can't read it: the founder does
        logger.warning("reply read failed: %s", exc)
        return ReplyResult("hold", None, "ReachAI couldn't read this reply right now. Read it yourself, or try again in a minute.")
    if signals["opt_out"] >= R.OPT_OUT_FROM:
        return ReplyResult("opt_out", None, "They asked not to be contacted again. ReachAI won't email them.", signals=signals)
    if signals["injection"] > R.INJECTION_ABOVE:
        return ReplyResult("hold", None, "Their message contains instructions aimed at an AI. Read it yourself.", signals=signals)

    if read_only:
        return ReplyResult("agent_task", None, "Your agent writes the reply on its schedule.", signals=signals)

    last: dict = {}

    async def write_draft(note: Optional[dict]) -> Optional[Draft]:
        d = await write(ctx, context, note)
        if d is not None:
            last["draft"] = d
        return d

    asks = signals.get("asks_question", 1.0) >= R.ASKS_QUESTION_FROM

    async def review(d: Draft):
        return await J.rubric(ctx, d, judge, asks_question=asks)

    out = await run(CheckedTask(name=f"reply:{ctx.mode}", write=write_draft, limits=lambda d: J.limits(ctx, d),
                                review=review, show=_show, max_rewrites=R.MAX_REWRITES,
                                # held for the founder: the last draft still helps (shown with what failed)
                                fallback=lambda history, why: last.get("draft")))
    return outcome(ctx, out, signals, today=today)


async def review_draft(ctx: ReplyContext, draft: Draft, signals: dict, *, judge, tries: int, max_tries: int, today: Optional[date] = None) -> tuple[Optional[ReplyResult], list[dict], dict]:
    """One review of a draft the founder's own agent wrote: the same hard limits (code) and Jev rubric our own writer's
    drafts get. → (result when it passed, or when the tries are used up and the founder gets the last draft;
    problems to send back; what was right). `tries` counts this one."""
    from app.agents.checked_writer import Review

    today = today or date.today()
    problems = J.limits(ctx, draft)
    review = Review()
    if not problems:
        review = await J.rubric(ctx, draft, judge, asks_question=signals.get("asks_question", 1.0) >= R.ASKS_QUESTION_FROM)
        problems = list(review.critical)
    if review.stop:
        problems = problems or [{"check": review.stop}]
    if not problems:
        out = Outcome(output=draft, source="ai", rounds=tries, history=[], review=review)
        return outcome(ctx, out, signals, today=today), [], review.right
    if tries >= max_tries:  # the founder gets the last draft, held, with what failed (like our own writer's fallback)
        out = Outcome(output=draft, source="fallback", rounds=tries, why="failed", review=review,
                      history=[{"draft": _show(draft), "critical": problems, "minor": review.minor}])
        return outcome(ctx, out, signals, today=today), problems, review.right
    return None, problems, review.right
