"""The "Why this creator" loop (decided Nov 15): Jev picks the facts → the LLM writes 3 bullets → Jev checks them →
a critical miss goes back to the LLM with the facts, its last bullets, what was right and what to fix (at most
twice) → still wrong: the facts themselves are shown (never wrong, just plainer).

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
    if GENDERED.search(" ".join(bullets)):
        critical.append({"check": "guesses the creator's gender: call them 'they'"})
    want_weak = points["watch"]["kind"] == "weakness"
    w = j.noul("is_weakness")
    if (w >= K.REASON_WATCH_KIND_FROM) != want_weak:
        critical.append({"bullet": 2, "check": "should be a weakness" if want_weak else "should be a strength, not a weakness",
                         "score": round(w, 2)})
    return critical, minor, right


def feedback_prompt(base_prompt: str, last: list[str], critical: list[dict], right: dict) -> str:
    """The reviewer note: separate from the task, with the history of the last try."""
    note = {"your_last_bullets": last, "what_was_right": right, "fix_these": critical}
    return (base_prompt + "\n\nREVIEWER NOTE on your last answer (not part of the facts): "
            + json.dumps(note, ensure_ascii=False) + "\nFix every point in fix_these, keep what was right, and answer again "
            "with only the 3 lines.")


async def write_checked(base_prompt: str, points: dict, verdict: Optional[str], *, write: Write, judge: Optional[Judge],
                        parse: Callable[[str], list[str]]) -> Result:
    """`write(prompt)` → model text; `judge(state, questions)` → Jev judgment (None: Jev down, no check)."""
    from app.judge.questions import reason_check_questions

    history: list[dict] = []
    prompt = base_prompt
    for rnd in range(1, K.REASON_MAX_REWRITES + 2):
        try:
            bullets = parse(await write(prompt))
        except Exception as exc:  # noqa: BLE001 - every model failed
            logger.warning("reason writer failed: %s", exc)
            break
        if len(bullets) != 3:
            history.append({"bullets": bullets, "critical": [{"check": "not 3 bullets"}]})
            prompt = feedback_prompt(base_prompt, bullets, [{"check": "answer with exactly 3 lines starting with '- '"}], {})
            continue
        if judge is None:
            return Result(bullets, "ai", rnd, history=history)
        try:
            j = await judge(check_state(points, verdict, bullets), reason_check_questions())
        except Exception as exc:  # noqa: BLE001 - can't check: the facts are always right
            logger.warning("reason check failed: %s", exc)
            break
        if j.noul("injection") > K.DROP_INJECTION_ABOVE:
            break
        critical, minor, right = verdict_of(j, points, bullets)
        history.append({"bullets": bullets, "critical": critical, "minor": minor})
        if not critical:
            return Result(bullets, "ai", rnd, minor=minor, history=history)
        prompt = feedback_prompt(base_prompt, bullets, critical, right)
    return Result(fact_bullets(points), "facts", len(history) or 1, history=history)
