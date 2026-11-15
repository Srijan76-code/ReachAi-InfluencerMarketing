"""What the "Why this creator" bullets say (decided Nov 15, docs/MODEL_BENCHMARKS.md):

1. code lists the true facts (from Jev's earlier answers and our badges): every reason they fit, every weakness,
   every extra strength, and their recent titles. Nothing here is inferred.
2. Jev picks, in one request: the strongest reason, the title that best shows the fit, and which weakness
   matters most for this brief (or another strength when there's none).
3. the LLM words the picks: why · watch out · when to choose.
4. Jev checks the bullets (app/discovery/reason_check.py); a critical miss goes back with feedback.

`pick` is the fixed-priority fallback, used only when Jev is down."""

from __future__ import annotations

import re
from typing import Optional

GOAL_WORDS = {"signups": "signups", "sales": "sales", "awareness": "awareness", "traffic": "website visits"}
NO_WEAKNESS = "No clear weakness in what we checked"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())}


def evidence_titles(titles: list[str], topics: list[str], n: int = 2) -> list[str]:
    """Their post titles that share the most words with the brief's topics (fallback only)."""
    want = set().union(*(_words(t) for t in topics)) if topics else set()
    scored = sorted(((len(_words(t) & want), i, t) for i, t in enumerate(titles) if t), key=lambda x: (-x[0], x[1]))
    return [t for s, _, t in scored if s > 0][:n]


def facts(signals: dict, flags: list[str], *, metrics: Optional[dict] = None, competitor_promos: Optional[list] = None,
          competitor_mode: str = "show", persona: str = "") -> dict:
    """Every true statement we can make, by slot, most serious first. → {"why": [...], "weak": [...], "strong": [...]}"""
    m = metrics or {}
    audience, topic = signals.get("audience match"), signals.get("topic match")
    problems = signals.get("covers the audience's problems")
    flags = set(flags or [])
    why = []
    if audience == "high" and topic == "high":
        why.append("Their audience is the buyers and their content is on the product's topic")
    if audience == "high":
        why.append(f"Their audience is the buyers ({persona})" if persona else "Their audience is the buyers")
    if topic == "high":
        why.append("Their content is on the product's topic")
    if problems == "high":
        why.append("They talk about the problem the product solves")
    if audience == "medium" or topic == "medium":
        why.append("Their audience and content partly match the product")
    if not why:
        why.append("Some of their content touches the product's topic")
    weak = []
    if "suspicious" in flags:
        weak.append("Their likes and comments look unusual for their size: ask for audience stats before paying")
    if competitor_promos and competitor_mode != "prefer":
        weak.append(f"They recently promoted a competitor ({competitor_promos[0].get('brand')})")
    if audience == "low":
        weak.append("Their audience isn't the buyers the brief describes")
    if topic == "low":
        weak.append("Most of their content is on other topics")
    if "country_unknown" in flags:
        weak.append("Where their audience lives isn't clear")
    if m.get("reliability") == "Low":
        weak.append("Their views swing a lot from post to post")
    if problems == "low" and audience != "low":
        weak.append("They rarely talk about the problem the product solves")
    strong = []
    if "rising" in flags:
        strong.append("Their recent posts are doing better than usual")
    if "trend" in flags:
        strong.append("They post about what their niche is talking about right now")
    if competitor_promos and competitor_mode == "prefer":
        strong.append(f"They already promoted a competitor ({competitor_promos[0].get('brand')}), so they take deals in this space")
    if m.get("reliability") == "High":
        strong.append("Their views are steady from post to post")
    return {"why": why, "weak": weak, "strong": strong}


def choose(verdict: Optional[str], flags: list[str], goal: Optional[str]) -> str:
    """When to pick them: follows our verdict (a number decision made in code) and badges."""
    flags = set(flags or [])
    g = GOAL_WORDS.get(goal or "", goal or "the campaign")
    if "suspicious" in flags and verdict != "Avoid":
        return "Only after they share their audience stats"
    if verdict == "Strong Buy":
        return f"A core creator for {g}" + (": book early, before their rate goes up" if "rising" in flags else "")
    if verdict == "Consider":
        return "A small test deal first" + (", booked early while they're rising" if "rising" in flags else "")
    return "Skip unless you need this audience specifically"


def about_content(why: str) -> bool:
    """A post title shows what they post about, never who watches: proof only goes with a content reason."""
    return bool(re.search(r"content|topic|talk about", why or "", re.I))


def slots(why: str, proof: Optional[str], watch_kind: str, watch_fact: str, choose_fact: str) -> dict:
    return {"why": why, "proof": proof if about_content(why) else None,
            "watch": {"kind": watch_kind, "fact": watch_fact}, "choose": choose_fact}


def pick(signals: dict, flags: list[str], verdict: Optional[str], *, metrics: Optional[dict] = None,
         goal: Optional[str] = None, competitor_promos: Optional[list] = None, competitor_mode: str = "show",
         titles: Optional[list[str]] = None, topics: Optional[list[str]] = None, persona: str = "") -> dict:
    """Fallback without Jev: the first fact of each list. One fact per bullet."""
    f = facts(signals, flags, metrics=metrics, competitor_promos=competitor_promos, competitor_mode=competitor_mode,
              persona=persona)
    # a title shows what they post about, not who watches: only offered when their topic fits
    proof = evidence_titles(titles or [], topics or [], n=1) if signals.get("topic match") != "low" else []
    if f["weak"]:
        kind, fact = "weakness", f["weak"][0]
    else:
        kind, fact = "strength", (f["strong"][0] if f["strong"] else NO_WEAKNESS)
    return slots(f["why"][0], proof[0] if proof else None, kind, fact, choose(verdict, flags, goal))


def from_jev(answers: dict, f: dict, titles: list[str], verdict: Optional[str], flags: list[str],
             goal: Optional[str], fallback: dict) -> dict:
    """Jev's picks (Choice keys "o0".., "t0".., "w0".., "s0".., or "none") back into facts. Anything Jev didn't
    answer falls back to the code pick."""
    def idx(key, prefix, items):
        v = str(answers.get(key) or "")
        if v.startswith(prefix) and v[len(prefix):].isdigit() and int(v[len(prefix):]) < len(items):
            return items[int(v[len(prefix):])]
        return None

    why = idx("why", "o", f["why"]) or fallback["why"]
    proof = idx("proof", "t", titles) if "proof" in answers else fallback["proof"]
    if f["weak"]:
        kind, fact = "weakness", idx("weak", "w", f["weak"]) or fallback["watch"]["fact"]
    else:
        kind, fact = "strength", idx("strong", "s", f["strong"]) or fallback["watch"]["fact"]
    return slots(why, proof, kind, fact, choose(verdict, flags, goal))
