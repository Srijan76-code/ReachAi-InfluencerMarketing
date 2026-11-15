"""The checked writer: one LangGraph agent for every "an LLM writes, Jev checks" task (decided Nov 15).

    write ─► check ─┬─ passed ─────────────────────────────► done   (source "ai")
      ▲             ├─ critical, rewrites left ─► note ─┐
      └─────────────┼───────────────────────────────────┘
                    └─ critical and no rewrites left,
                       writer or checker down, or stop ─► fallback (source "fallback")

- `check` runs the task's code `limits` first (exact rules: prices, pronouns, format). Only when they pass does it
  ask the task's `review` (Jev's rubric), so a draft that breaks an exact rule never costs a Jev call.
- Critical problems go back to the writer as a reviewer note, kept apart from the task itself:
  `{"your_last_draft", "what_was_right", "fix_these"}`. Minor problems pass ("mostly right lets it pass").
- `fallback` gets the whole history (every draft and why it failed) and decides what to show instead: the plain
  facts, a template, or the best draft held for the founder.

Each use passes its own `CheckedTask` (instructions live in the task's `write`, the rubric in its `review`), so
"why this creator", replies and follow-ups are the same agent with different settings. Runs are short, so no
checkpointer; LangSmith traces each run under the task's name."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, Optional, TypedDict, TypeVar

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)
D = TypeVar("D")

DEFAULT_MAX_REWRITES = 2  # research and our own runs: 2 rewrites fix nearly everything that can be fixed


@dataclass
class Review:
    """What a checker found. `critical`: [{"check", "why", "score"?, ...}] (sent back); `minor`: passes anyway.
    `stop`: give up without rewriting (e.g. a prompt injection in the input). `signals`: extra readings the
    caller needs (e.g. "the creator asked to stop")."""
    critical: list[dict] = field(default_factory=list)
    minor: list[str] = field(default_factory=list)
    right: dict = field(default_factory=dict)
    stop: Optional[str] = None
    signals: dict = field(default_factory=dict)


@dataclass
class CheckedTask(Generic[D]):
    name: str
    write: Callable[[Optional[dict]], Awaitable[Optional[D]]]  # reviewer note (None on the first try) → draft
    fallback: Callable[[list[dict], Optional[str]], Any]  # (history, why) → what to use instead
    limits: Callable[[D], list[dict]] = lambda d: []  # exact code rules → critical problems
    review: Optional[Callable[[D], Awaitable[Review]]] = None  # the rubric (Jev); None: code limits only
    show: Callable[[D], Any] = lambda d: d  # how a draft appears in the reviewer note and the history
    max_rewrites: int = DEFAULT_MAX_REWRITES


@dataclass
class Outcome(Generic[D]):
    output: Any  # the passing draft, or what `fallback` returned
    source: str  # ai | fallback
    rounds: int
    history: list[dict]  # [{"draft", "critical", "minor"}] for each try
    review: Optional[Review] = None  # the last review (its signals stay useful after a fallback)
    why: Optional[str] = None  # why it fell back: failed | writer_down | checker_down | stop:<reason>


class _State(TypedDict, total=False):
    draft: Any
    review: Optional[Review]
    note: Optional[dict]
    rounds: int
    history: list
    outcome: Outcome
    why: Optional[str]


def _task(config) -> CheckedTask:
    return config["configurable"]["task"]


async def _write(s: _State, config) -> _State:
    t = _task(config)
    try:
        draft = await t.write(s.get("note"))
    except Exception as exc:  # noqa: BLE001 - every model failed
        logger.warning("%s: writer failed: %s", t.name, exc)
        draft = None
    return {"draft": draft, "rounds": s.get("rounds", 0) + 1, "why": None if draft is not None else "writer_down"}


async def _check(s: _State, config) -> _State:
    t, draft = _task(config), s["draft"]
    critical = list(t.limits(draft))
    review = Review()
    if not critical and t.review is not None:
        try:
            review = await t.review(draft)
        except Exception as exc:  # noqa: BLE001 - can't check it: never pass it as checked
            logger.warning("%s: checker failed: %s", t.name, exc)
            hist = [*s.get("history", []), {"draft": t.show(draft), "critical": [{"check": "unchecked"}], "minor": []}]
            return {"review": None, "history": hist, "why": "checker_down"}
        critical = review.critical
    review = Review(critical=critical, minor=review.minor, right=review.right, stop=review.stop, signals=review.signals)
    hist = [*s.get("history", []), {"draft": t.show(draft), "critical": critical, "minor": review.minor}]
    return {"review": review, "history": hist, "why": f"stop:{review.stop}" if review.stop else None}


def _after_write(s: _State) -> str:
    return "check" if s.get("draft") is not None else "fallback"


def _after_check(s: _State, config) -> str:
    r = s.get("review")
    if r is None or r.stop:
        return "fallback"
    if not r.critical:
        return "done"
    return "note" if s["rounds"] <= _task(config).max_rewrites else "fallback"


async def _note(s: _State, config) -> _State:
    r = s["review"]
    return {"note": {"your_last_draft": _task(config).show(s["draft"]), "what_was_right": r.right, "fix_these": r.critical}}


async def _done(s: _State, config) -> _State:
    return {"outcome": Outcome(s["draft"], "ai", s["rounds"], s.get("history", []), s.get("review"))}


async def _fallback(s: _State, config) -> _State:
    t = _task(config)
    why = s.get("why") or "failed"
    return {"outcome": Outcome(t.fallback(s.get("history", []), why), "fallback", s.get("rounds", 1),
                               s.get("history", []), s.get("review"), why)}


def build():
    g = StateGraph(_State)
    for name, fn in (("write", _write), ("check", _check), ("note", _note), ("done", _done), ("fallback", _fallback)):
        g.add_node(name, fn)
    g.set_entry_point("write")
    g.add_conditional_edges("write", _after_write, {"check": "check", "fallback": "fallback"})
    g.add_conditional_edges("check", _after_check, {"done": "done", "note": "note", "fallback": "fallback"})
    g.add_edge("note", "write")
    g.add_edge("done", END)
    g.add_edge("fallback", END)
    return g.compile()


_GRAPH = None


async def run(task: CheckedTask) -> Outcome:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build()
    final = await _GRAPH.ainvoke({"rounds": 0, "history": []},
                                 config={"configurable": {"task": task}, "run_name": f"checked:{task.name}",
                                         "recursion_limit": 4 * (task.max_rewrites + 2)})
    return final["outcome"]
