"""The "Why this creator" settings for the checked writer (app/agents/checked_writer.py, decided Nov 15): Jev picks
the facts → the LLM writes 3 bullets → code and Jev check them → a critical miss goes back to the LLM with the facts,
its last bullets, what was right and what to fix (at most twice) → still wrong: the facts themselves are shown
(never wrong, just plainer).

Critical (rewrite): a bullet states something not in the facts; the bullets contradict the verdict; bullet 2
reads as a weakness when the fact isn't one, or the other way round; a quoted title used as proof of something
it doesn't show (prevented upstream: titles only go with content reasons); the creator's gender is guessed
(an exact word check in code). Minor (passes): two points in one bullet."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from app.judge import constants as K

logger = logging.getLogger(__name__)

Judge = Callable[[dict, dict], Awaitable[object]]
Write = Callable[[str], Awaitable[str]]


@dataclass
class Result:
    bullets: list[str]
    source: str  # ai | facts
    rounds: int = 1
    minor: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)  # each round's bullets and what failed


def fact_bullets(points: dict) -> list[str]:
    """The facts as bullets, no model involved (the last resort)."""
    w = points["watch"]
    why = points["why"] + (f', e.g. "{points["proof"]}"' if points.get("proof") else "")
    return [why + ".", ("Watch out: " if w["kind"] == "weakness" else "") + w["fact"] + ".", points["choose"] + "."]


def check_state(points: dict, verdict: Optional[str], bullets: list[str]) -> dict:
    return {"facts": points, "verdict": verdict or "Consider", "bullets": (bullets + ["", "", ""])[:3]}


GENDERED = re.compile(r"\b(he|she|him|his|her|hers|himself|herself)\b", re.I)  # exact: a code check, not a judgment


def verdict_of(j, points: dict, bullets: list[str]) -> tuple[list[dict], list[str], dict]:
    """(critical problems, minor problems, what was right) from Jev's check."""
    critical, minor, right = [], [], {}
    for i in range(3):
        g = j.noul(f"grounded_{i}")
        if g < K.REASON_GROUNDED_MIN:
            critical.append({"bullet": i + 1, "check": "states something not in the facts", "score": round(g, 2)})
        else:
            right[f"bullet {i + 1}"] = "sticks to the facts"
        if j.noul(f"one_point_{i}") > K.REASON_ONE_POINT_MAX:
            minor.append(f"bullet {i + 1} makes two points")
    a = j.noul("agrees")
    if a < K.REASON_AGREES_MIN:
        critical.append({"check": "contradicts the verdict", "score": round(a, 2)})
    else:
        right["verdict"] = "agrees with the verdict"
    want_weak = points["watch"]["kind"] == "weakness"
    w = j.noul("is_weakness")
    if (w >= K.REASON_WATCH_KIND_FROM) != want_weak:
        critical.append({"bullet": 2, "check": "should be a weakness" if want_weak else "should be a strength, not a weakness",
                         "score": round(w, 2)})
    return critical, minor, right


def limits(bullets: list[str]) -> list[dict]:
    """Exact rules, checked in code before Jev is asked."""
    if len(bullets) != 3:
        return [{"check": "answer with exactly 3 lines starting with '- '"}]
    if GENDERED.search(" ".join(bullets)):
        return [{"check": "guesses the creator's gender: call them 'they'"}]
    return []


def feedback_prompt(base_prompt: str, last: list[str], critical: list[dict], right: dict) -> str:
    """The reviewer note: separate from the task, with the history of the last try."""
    note = {"your_last_bullets": last, "what_was_right": right, "fix_these": critical}
    return (base_prompt + "\n\nREVIEWER NOTE on your last answer (not part of the facts): "
            + json.dumps(note, ensure_ascii=False) + "\nFix every point in fix_these, keep what was right, and answer again "
            "with only the 3 lines.")


async def write_checked(base_prompt: str, points: dict, verdict: Optional[str], *, write: Write, judge: Optional[Judge],
                        parse: Callable[[str], list[str]]) -> Result:
    """`write(prompt)` → model text; `judge(state, questions)` → Jev judgment (None: Jev down, no check)."""
    from app.agents.checked_writer import CheckedTask, Review, run
    from app.judge.questions import reason_check_questions

    async def write_bullets(note: Optional[dict]) -> list[str]:
        prompt = base_prompt if note is None else feedback_prompt(base_prompt, note["your_last_draft"], note["fix_these"],
                                                                  note["what_was_right"])
        return parse(await write(prompt))

    async def review(bullets: list[str]) -> Review:
        j = await judge(check_state(points, verdict, bullets), reason_check_questions())
        if j.noul("injection") > K.DROP_INJECTION_ABOVE:
            return Review(stop="injection")
        critical, minor, right = verdict_of(j, points, bullets)
        return Review(critical=critical, minor=minor, right=right)

    out = await run(CheckedTask(name="reasons", write=write_bullets, limits=limits, review=review if judge else None,
                                fallback=lambda history, why: fact_bullets(points), max_rewrites=K.REASON_MAX_REWRITES))
    if out.source == "ai":
        return Result(out.output, "ai", out.rounds, minor=out.review.minor if out.review else [], history=out.history)
    if out.why not in (None, "failed"):
        logger.warning("reason bullets fell back to the facts: %s", out.why)
    return Result(out.output, "facts", out.rounds, history=out.history)
