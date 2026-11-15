"""The "Why this creator" loop: the LLM writes, Jev checks, a critical miss goes back with feedback (the facts,
the last bullets, what was right, what to fix); minor issues pass; still wrong → the facts themselves."""

import json

import pytest

from app.discovery.prompts import reason_bullets
from app.discovery.reason_check import fact_bullets, write_checked
from app.judge.client import Answer, Judgment

pytestmark = pytest.mark.asyncio
POINTS = {"why": "Their audience is the buyers", "proof": "My 5AM routine", "watch": {"kind": "weakness", "fact": "Where their audience lives isn't clear"},
          "choose": "A small test deal first"}


def jev(grounded=(0.9, 0.9, 0.9), agrees=0.9, is_weak=0.9, one_point=(0.1, 0.1, 0.1)):
    async def judge(state, questions):
        a = {f"grounded_{i}": Answer("noul", g) for i, g in enumerate(grounded)}
        a.update({f"one_point_{i}": Answer("noul", o) for i, o in enumerate(one_point)})
        a.update(agrees=Answer("noul", agrees), is_weakness=Answer("noul", is_weak), injection=Answer("noul", 0.0))
        judge.calls.append(state)
        return Judgment(a, "sim", "jev")
    judge.calls = []
    return judge


def writer(*answers):
    prompts = []

    async def write(p):
        prompts.append(p)
        return answers[min(len(prompts) - 1, len(answers) - 1)]
    write.prompts = prompts
    return write


GOOD = "- Their viewers are the buyers, and they post \"My 5AM routine\".\n- Watch out: where their audience lives isn't clear.\n- A small test deal first."


async def test_passes_first_time_and_minor_issues_pass():
    w = writer(GOOD)
    r = await write_checked("BASE", POINTS, "Consider", write=w, judge=jev(one_point=(0.9, 0.1, 0.1)), parse=reason_bullets)
    assert r.source == "ai" and r.rounds == 1 and len(w.prompts) == 1 and r.minor == ["bullet 1 makes two points"]


async def test_a_critical_miss_goes_back_with_history_and_feedback():
    calls = {"n": 0}
    base = jev()

    async def judge(state, qs):
        calls["n"] += 1
        return await (jev(grounded=(0.2, 0.9, 0.9)) if calls["n"] == 1 else base)(state, qs)

    bad = "- They are huge in the US and Lumen fans.\n- Watch out: unclear country.\n- A small test deal first."
    w = writer(bad, GOOD)
    r = await write_checked("BASE", POINTS, "Consider", write=w, judge=judge, parse=reason_bullets)
    assert r.source == "ai" and r.rounds == 2
    note = json.loads(w.prompts[1].split("REVIEWER NOTE on your last answer (not part of the facts): ", 1)[1].split("\n", 1)[0])
    assert note["your_last_bullets"][0].startswith("They are huge")  # its own last answer (the history)
    assert note["fix_these"] == [{"bullet": 1, "check": "states something not in the facts", "score": 0.2}]
    assert note["what_was_right"]["bullet 2"] == "sticks to the facts" and "verdict" in note["what_was_right"]
    assert w.prompts[1].startswith("BASE")  # the facts are sent again, unchanged


async def test_wrong_slot_and_verdict_are_critical_then_the_facts_are_shown():
    w = writer(GOOD)
    r = await write_checked("BASE", POINTS, "Consider", write=w, judge=jev(agrees=0.1, is_weak=0.1), parse=reason_bullets)
    assert r.source == "facts" and len(w.prompts) == 3  # first try + 2 rewrites
    assert r.bullets == fact_bullets(POINTS)
    assert r.bullets[0] == 'Their audience is the buyers, e.g. "My 5AM routine".' and r.bullets[1].startswith("Watch out: ")
    checks = {c["check"] for c in r.history[0]["critical"]}
    assert checks == {"contradicts the verdict", "should be a weakness"}


async def test_a_strength_must_not_read_as_a_weakness():
    pts = {**POINTS, "watch": {"kind": "strength", "fact": "Their recent posts are doing better than usual"}}
    r = await write_checked("BASE", pts, "Strong Buy", write=writer(GOOD), judge=jev(is_weak=0.9), parse=reason_bullets)
    assert r.source == "facts" and r.history[0]["critical"][0]["check"] == "should be a strength, not a weakness"


async def test_bad_format_and_outages():
    r = await write_checked("BASE", POINTS, "Consider", write=writer("Just one sentence."), judge=jev(), parse=reason_bullets)
    assert r.source == "facts"

    async def down(p):
        raise RuntimeError("all models down")
    r = await write_checked("BASE", POINTS, "Consider", write=down, judge=jev(), parse=reason_bullets)
    assert r.source == "facts" and r.bullets == fact_bullets(POINTS)

    async def jev_down(s, q):
        raise RuntimeError("jev down")
    r = await write_checked("BASE", POINTS, "Consider", write=writer(GOOD), judge=jev_down, parse=reason_bullets)
    assert r.source == "facts"  # unchecked text is never shown


async def test_a_guessed_gender_goes_back():
    she = GOOD.replace("Their viewers", "Her viewers")
    w = writer(she, GOOD)
    r = await write_checked("BASE", POINTS, "Consider", write=w, judge=jev(), parse=reason_bullets)
    assert r.rounds == 2 and r.history[0]["critical"] == [{"check": "guesses the creator's gender: call them 'they'"}]


async def test_titles_only_back_up_content_reasons():
    from app.discovery.reason_points import slots
    assert slots("Their audience is the buyers", "My 5AM routine", "strength", "x", "y")["proof"] is None
    assert slots("Their content is on the product's topic", "My 5AM routine", "strength", "x", "y")["proof"] == "My 5AM routine"
