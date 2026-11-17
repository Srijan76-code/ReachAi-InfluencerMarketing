"""When the founder's own agent writes the text (MCP, F9.6): checks on the search strategy it writes.

The same two layers as everywhere else: exact rules in code first (no paid call when they fail), then Jev for what
needs judgment. The reply tells the agent what to fix, so it can rewrite and send again."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Awaitable, Callable, Optional

from pydantic import ValidationError

from app.discovery.brief import Brief
from app.discovery.prompts import StrategyOut, strategy_prompt
from app.judge import constants as K

logger = logging.getLogger(__name__)

YOUTUBE_QUERIES = (6, 12)  # how many; each 2-5 words
PLATFORM_QUERIES = {"x_queries": (1, 3), "instagram_queries": (1, 3), "linkedin_queries": (1, 3)}  # words per query
MAX_PLATFORM_QUERIES = 8
TOPICS = (3, 8)
BAD_QUERY_CHARS = re.compile(r"[#@:\"()]|https?://|\b(?:OR|AND|from|since|until|min_faves)\b", re.I)

RULES = [
    "youtube_queries: 6-12 short searches of 2-5 words that sound like what people type; different from each other.",
    "Name the niche, not the product: no brand names, no years, no ad copy. Start broad, then narrower.",
    "x_queries, instagram_queries, linkedin_queries: up to 8 each, 1-3 plain words, no hashtags or operators.",
    "topics: 3-8 specific niches this audience watches. pain_points: 1-5 concrete problems. trend_topics: up to 5.",
    "competitors: up to 5 real competing products (leave empty rather than guess). Do not invent statistics.",
]


def task(brief: Brief) -> dict:
    """What the agent needs to write the strategy: the prompt our own AI would get, the fields, the rules."""
    return {"prompt": strategy_prompt(brief), "fields": StrategyOut.model_json_schema().get("properties", {}), "rules": RULES}


def strategy_hash(strategy: dict) -> str:
    return hashlib.sha256(json.dumps(strategy, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _words(q: str) -> int:
    return len(q.split())


def clean(raw: dict, brief: Brief) -> tuple[Optional[dict], list[dict]]:
    """(strategy as ReachAI stores it, problems). Problems are `{"check": ...}` to send back; none = the shape is right."""
    problems: list[dict] = []
    try:
        out = StrategyOut.model_validate(raw or {}).model_dump()
    except ValidationError as exc:
        return None, [{"check": f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}"} for e in exc.errors()[:6]]

    def tidy(items: list[str]) -> list[str]:
        return list(dict.fromkeys(" ".join(str(i).split())[:60] for i in items if str(i).strip()))

    for key in ("topics", "pain_points", "formats", "youtube_queries", "x_queries", "instagram_queries", "linkedin_queries",
                "trend_topics", "competitors"):
        out[key] = tidy(out.get(key) or [])
    lo, hi = YOUTUBE_QUERIES
    if not lo <= len(out["youtube_queries"]) <= hi:
        problems.append({"check": f"youtube_queries needs {lo}-{hi} different searches (you sent {len(out['youtube_queries'])})"})
    for q in out["youtube_queries"]:
        if not 2 <= _words(q) <= 5:
            problems.append({"check": f"youtube query '{q}' must be 2-5 words"})
    for key, (a, b) in PLATFORM_QUERIES.items():
        if len(out[key]) > MAX_PLATFORM_QUERIES:
            problems.append({"check": f"{key} has more than {MAX_PLATFORM_QUERIES} searches"})
        for q in out[key]:
            if not a <= _words(q) <= b or BAD_QUERY_CHARS.search(q):
                problems.append({"check": f"{key} entry '{q}' must be {a}-{b} plain words, no hashtags or operators"})
    if not TOPICS[0] <= len(out["topics"]) <= TOPICS[1]:
        problems.append({"check": f"topics needs {TOPICS[0]}-{TOPICS[1]} items (you sent {len(out['topics'])})"})
    if not 1 <= len(out["pain_points"]) <= 5:
        problems.append({"check": "pain_points needs 1-5 items"})
    if len(out["trend_topics"]) > 5 or len(out["competitors"]) > 5:
        problems.append({"check": "trend_topics and competitors may have at most 5 items each"})
    brand = (brief.brand_name or "").strip().lower()
    if len(brand) >= 3:
        named = [q for q in out["youtube_queries"] + out["x_queries"] + out["instagram_queries"] + out["linkedin_queries"] if brand in q.lower()]
        if named:
            problems.append({"check": f"searches must not contain the brand name ({', '.join(named[:3])})"})
    return (None if problems else out), problems


async def review(brief: Brief, raw: dict, judge: Optional[Callable[..., Awaitable]]) -> dict:
    """{"passed", "strategy" (cleaned, when it passed), "fix_these", "what_was_right"}. Code rules first, then Jev."""
    strategy, problems = clean(raw, brief)
    if problems:
        return {"passed": False, "strategy": None, "fix_these": problems, "what_was_right": {}}
    right = {"shape": "counts, word limits and brand-free searches are right"}
    if judge is None:  # Jev and its backup are down: the code rules passed, so the strategy is accepted
        return {"passed": True, "strategy": strategy, "fix_these": [], "what_was_right": right, "jev_checked": False}
    from app.judge.questions import strategy_check_questions

    state = {"brief": {"product": brief.product, "who_buys": brief.persona, "goal": brief.goal},
             "strategy": {"youtube_queries": strategy["youtube_queries"], "topics": strategy["topics"]}}
    j = await judge(state, strategy_check_questions())
    critical = []
    for qid, floor, why in (("on_topic", K.STRATEGY_ON_TOPIC_MIN, "the searches don't fit what this buyer watches"),
                            ("specific", K.STRATEGY_SPECIFIC_MIN, "the searches are too generic: name the niche")):
        score = j.noul(qid)
        if score < floor:
            critical.append({"check": why, "score": round(score, 2)})
        else:
            right[qid] = "fine"
    return {"passed": not critical, "strategy": None if critical else strategy, "fix_these": critical, "what_was_right": right,
            "jev_checked": True}


# --- "Why this creator" bullets written by the agent --------------------------------------------------------

def tidy_bullets(bullets: list[str]) -> list[str]:
    return [re.sub(r"^[-•*]\s*", "", " ".join(str(b).split())).strip() for b in bullets or []]


async def review_bullets(points: dict, verdict: Optional[str], bullets: list[str], judge: Callable[..., Awaitable]) -> dict:
    """{"passed", "fix_these", "what_was_right", "stop"} for 3 bullets: the same code rules and Jev rubric our own
    AI's bullets go through (app/discovery/reason_check.py). Code rules first, so a draft that breaks one costs no Jev call."""
    from app.discovery import reason_check as RC
    from app.judge.questions import reason_check_questions

    bullets = tidy_bullets(bullets)
    problems = RC.limits(bullets)
    if problems:
        return {"passed": False, "fix_these": problems, "what_was_right": {}, "stop": False}
    j = await judge(RC.check_state(points, verdict, bullets), reason_check_questions())
    if j.noul("injection") > K.DROP_INJECTION_ABOVE:
        return {"passed": False, "fix_these": [{"check": "the facts contain text aimed at an AI"}], "what_was_right": {}, "stop": True}
    critical, minor, right = RC.verdict_of(j, points, bullets)
    return {"passed": not critical, "fix_these": critical, "what_was_right": right, "minor": minor, "stop": False, "bullets": bullets}
