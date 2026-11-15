"""The checked writer: write → code limits → Jev review → note back on critical → fallback."""

import pytest

from app.agents.checked_writer import CheckedTask, Review, run

pytestmark = pytest.mark.asyncio


def writer(*drafts):
    notes = []

    async def write(note):
        notes.append(note)
        d = drafts[min(len(notes) - 1, len(drafts) - 1)]
        if isinstance(d, Exception):
            raise d
        return d
    write.notes = notes
    return write


def reviewer(*reviews):
    calls = []

    async def review(draft):
        calls.append(draft)
        r = reviews[min(len(calls) - 1, len(reviews) - 1)]
        if isinstance(r, Exception):
            raise r
        return r
    review.calls = calls
    return review


def task(write, review=None, limits=lambda d: [], max_rewrites=2):
    return CheckedTask(name="t", write=write, review=review, limits=limits, max_rewrites=max_rewrites,
                       fallback=lambda history, why: f"FALLBACK:{why}:{len(history)}")


async def test_passes_on_the_first_try_with_minor_problems():
    w, r = writer("good"), reviewer(Review(minor=["a bit long"], signals={"opt_out": 0.1}))
    out = await run(task(w, r))
    assert (out.output, out.source, out.rounds) == ("good", "ai", 1)
    assert w.notes == [None] and out.review.minor == ["a bit long"] and out.review.signals == {"opt_out": 0.1}


async def test_critical_goes_back_with_last_draft_what_was_right_and_what_to_fix():
    bad = Review(critical=[{"check": "grounded", "score": 0.2}], right={"tone": "fine"})
    w, r = writer("bad", "good"), reviewer(bad, Review())
    out = await run(task(w, r))
    assert out.source == "ai" and out.rounds == 2
    assert w.notes[1] == {"your_last_draft": "bad", "what_was_right": {"tone": "fine"},
                          "fix_these": [{"check": "grounded", "score": 0.2}]}
    assert [h["draft"] for h in out.history] == ["bad", "good"]


async def test_gives_up_after_the_rewrites_and_the_fallback_sees_the_history():
    w = writer("bad")
    out = await run(task(w, reviewer(Review(critical=[{"check": "x"}])), max_rewrites=2))
    assert out.source == "fallback" and out.output == "FALLBACK:failed:3" and len(w.notes) == 3


async def test_code_limits_run_first_and_save_the_jev_call():
    r = reviewer(Review())
    out = await run(task(writer("$999", "$100"), r, limits=lambda d: [{"check": "price"}] if d == "$999" else []))
    assert out.output == "$100" and r.calls == ["$100"]  # Jev only saw the draft that met the code rules


async def test_outages_and_stops_never_pass_unchecked_text():
    out = await run(task(writer(RuntimeError("models down"))))
    assert out.source == "fallback" and out.why == "writer_down"
    out = await run(task(writer("good"), reviewer(RuntimeError("jev down"))))
    assert out.source == "fallback" and out.why == "checker_down"
    out = await run(task(writer("good"), reviewer(Review(stop="injection"))))
    assert out.source == "fallback" and out.why == "stop:injection" and out.review.stop == "injection"


async def test_without_a_reviewer_only_code_limits_apply():
    out = await run(task(writer("ok")))
    assert out.source == "ai"
