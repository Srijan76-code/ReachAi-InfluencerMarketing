"""Fakes for running the whole discovery graph offline: recorded YouTube data, a keyword-based
fake Jev, a canned strategy, and deterministic embeddings."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from app.creators.constants import EMBEDDING_DIM
from app.discovery import limits as L
from app.discovery.prompts import ReasonOut, StrategyOut
from app.discovery.state import Deps
from app.judge.client import Answer, Judgment
from app.platforms.youtube import YouTubeAdapter
from scripts.record_youtube_fixtures import LIMITS as RECORDED_LIMITS
from scripts.record_youtube_fixtures import RECORDED_AT
from tests.platforms.youtube_replay import ReplayAPI

BRIEF = {
    "brand": {"name": "DataLaunch", "industry": "edtech", "business_model": "b2c", "product_price_range": "high_ticket",
              "core_outcome": "A 12-week data science bootcamp that guarantees a job or refunds tuition."},
    "audience": {"target_persona": "Fresh CS graduates moving into AI/ML roles", "locations": ["IN"], "languages": ["en", "hi"]},
    "campaign": {"goal": "signups", "creator_authority_level": "mentor", "budget_total": 5000, "creator_count": 5},
    "constraints": {"min_subscribers": 10000, "max_subscribers": 5000000, "target_countries": ["IN"], "exclude_kids_content": True},
}

STRATEGY = StrategyOut(
    topics=["data science career", "machine learning roadmap"],
    pain_points=["getting a first ML job"],
    formats=["tutorial"],
    youtube_queries=["machine learning roadmap for freshers"],  # matches the recording
    trend_topics=["AI agents"],
    competitors=["upGrad"],
    safety_level="medium",
    primary_metric="creator_authority",
)


def use_recorded_limits(monkeypatch):
    """The recording used a 2-search budget; make the 'full' branch ask for exactly that. All 100 search
    results become candidates (fused ranking would otherwise pick channels whose details weren't
    recorded); the 8 recorded channels are the ones the replayed channel lookups return."""
    monkeypatch.setitem(L.LIMITS_BY_MODE, "full", replace(RECORDED_LIMITS, region=None, max_candidates=100))


async def _no_cache(namespace, key, ttl, compute):
    return await compute(), False


class Counters(dict):
    def bump(self, k):
        self[k] = self.get(k, 0) + 1


def make_deps(session_factory, *, counters=None, fail_judge_times=0, jev_down=False, llm_down=False, yes_platforms=("youtube",)):
    counters = counters if counters is not None else Counters()
    state = {"judge_failures_left": fail_judge_times}

    def adapter():
        counters.bump("adapter_created")
        return YouTubeAdapter(ReplayAPI(), cache=_no_cache, now=lambda: RECORDED_AT)

    async def judge(st, questions):
        if "platform_youtube" in questions:
            counters.bump("platform_judge")
            if jev_down:
                raise RuntimeError("jev down")
            return Judgment({q: Answer("noul", 0.9 if q.removeprefix("platform_") in yes_platforms else 0.2) for q in questions}, "fake", "jev")
        counters.bump("creator_judge")
        if state["judge_failures_left"] > 0:
            state["judge_failures_left"] -= 1
            raise RuntimeError("crash while judging")
        text = (st["creator"]["display_name"] + " " + " ".join(st["creator"]["recent_posts"])).lower()
        ml = any(w in text for w in ("machine learning", " ml ", "ai ", "data science", "llm"))
        answers = {}
        for q, spec in questions.items():
            kind = spec.type if hasattr(spec, "type") else spec["type"]
            if kind == "score":
                levels = len(spec.criteria)
                answers[q] = Answer("score", float(levels - 1 if ml else 0) if q != "safety_risk" else 0.0)
            elif kind == "choice":
                answers[q] = Answer("choice", "ai_and_ml" if q == "niche" else "other")
            else:
                answers[q] = Answer("noul", {"is_individual": 0.95, "language_match": 0.95, "pain_point": 0.8 if ml else 0.1}.get(q, 0.05))
        return Judgment(answers, "fake-jev", "jev", input_tokens=100)

    async def llm(route, prompt, schema):
        counters.bump(f"llm:{route}")
        if llm_down:
            raise RuntimeError("llm down")
        if schema is StrategyOut:
            return STRATEGY
        return ReasonOut(reasoning="Their audience of new ML learners fits DataLaunch's job-guarantee bootcamp well.")

    async def embed(texts, task):
        counters.bump(f"embed:{task}")
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            v = [((h[i % len(h)] / 255.0) - 0.5) for i in range(EMBEDDING_DIM)]
            out.append(v)
        return out

    return Deps(adapters={"youtube": adapter}, session_factory=session_factory, judge=judge, llm=llm,
                embed=embed, now=lambda: RECORDED_AT), counters
