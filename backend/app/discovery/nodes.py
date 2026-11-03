"""Steps of the discovery graph (spec §4.14). Every step reads dependencies from the runtime
context (`Deps`), so tests swap in fakes and nothing heavy is checkpointed."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Send
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.billing.costs import CostContext
from app.creators import repository as repo
from app.discovery import limits as L
from app.discovery.brief import Brief
from app.discovery.legacy import to_legacy_lead
from app.discovery.prompts import (
    REASON_PROMPT_VERSION,
    STRATEGY_PROMPT_VERSION,
    ReasonOut,
    StrategyOut,
    reason_prompt,
    strategy_prompt,
)
from app.discovery.state import BranchState, Deps, DiscoveryState, ReasonState
from app.judge import constants as K
from app.judge.client import Judgment
from app.judge.combine import score_creator, select_platforms
from app.judge.questions import build_state, creator_questions, platform_questions
from app.metrics.compute import Metrics, compute_metrics, passes_gates
from app.models.discovery_run import RunCandidate, RunStrategy
from app.platforms.base import PLATFORMS, CandidateRef, Strategy

logger = logging.getLogger(__name__)


class JudgeStepError(RuntimeError):
    """Raised when a whole judging step fails, so the run retries and resumes from it."""


# --- helpers ---------------------------------------------------------------------------------------------


def _brief(state) -> Brief:
    return Brief(**state["brief"])


def _ctx(runtime: Runtime[Deps], state) -> CostContext:
    return runtime.context.cost_context or CostContext(run_id=state.get("run_id"), campaign_id=state.get("campaign_id"))


def _now(runtime: Runtime[Deps]) -> datetime:
    return runtime.context.now() if runtime.context.now else datetime.now(timezone.utc)


async def _llm(runtime: Runtime[Deps], route: str, prompt: str, schema, ctx: CostContext):
    if runtime.context.llm:
        return await runtime.context.llm(route, prompt, schema)
    from app.llm.client import achat

    return await achat(route, prompt, schema=schema, context=ctx)


async def _judge(runtime: Runtime[Deps], state: dict, questions: dict, ctx: CostContext) -> Judgment:
    if runtime.context.judge:
        return await runtime.context.judge(state, questions)
    from app.judge.client import judge

    return await judge(state, questions, context=ctx)


async def _embed(runtime: Runtime[Deps], texts: list[str], task: str, ctx: CostContext) -> list[list[float]]:
    if runtime.context.embed:
        return await runtime.context.embed(texts, task)
    from app.llm.embeddings import embed_texts

    return await embed_texts(texts, task=task, context=ctx, session_factory=runtime.context.session_factory)


def _emit(payload: dict) -> None:
    """Send a live event to the runner (custom stream). Ignored when nobody is listening."""
    try:
        get_stream_writer()(payload)
    except Exception:
        pass


def _strategy_obj(state) -> Strategy:
    s = state["strategy"]
    return Strategy(
        topics=s.get("topics", []),
        pain_points=s.get("pain_points", []),
        queries={"youtube": s.get("youtube_queries", [])},
        trend_topics=s.get("trend_topics", []),
        formats=s.get("formats", []),
        primary_metric=s.get("primary_metric", "engagement_depth"),
        safety_level=s.get("safety_level", "medium"),
    )


def _query_text(brief: Brief, strategy: dict) -> str:
    return " ".join(
        [brief.product, brief.persona, *strategy.get("topics", []), *strategy.get("pain_points", [])]
    ).strip()


def _creator_text(profile: dict) -> str:
    titles = " ".join(p.get("text", "") for p in (profile.get("recent_posts") or [])[:15])
    return f"{profile.get('display_name', '')} {(profile.get('bio') or '')[:300]} {titles}".strip()


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _signals(j: Judgment) -> dict:
    """Jev answers in plain words for the reason prompt (no raw numbers)."""
    def band(p):
        return "high" if p >= 0.7 else "medium" if p >= 0.4 else "low"

    out = {}
    if "topic_fit" in j.answers:
        out["topic match"] = band(j.score("topic_fit") / 4)
    if "audience_stage" in j.answers:
        out["audience match"] = band(j.score("audience_stage") / 3)
    if "pain_point" in j.answers:
        out["covers the audience's problems"] = band(j.noul("pain_point"))
    if "niche" in j.answers:
        out["niche"] = j.choice("niche")
    return out


# --- 1. strategy | platform_select | db_search  (run in parallel from START) ---------------------------------


async def strategy(state: DiscoveryState, runtime: Runtime[Deps]) -> dict:
    """One LLM call. Reused for an identical brief (same prompt version), so re-runs cost nothing."""
    brief = _brief(state)
    sf = runtime.context.session_factory
    reused = None
    try:
        from app.db.database import AsyncSessionLocal

        async with (sf or AsyncSessionLocal)() as session:
            reused = (
                await session.execute(
                    select(RunStrategy)
                    .where(RunStrategy.brief_hash == f"{STRATEGY_PROMPT_VERSION}:{brief.hash()}")
                    .order_by(RunStrategy.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
    except Exception:
        logger.exception("strategy reuse lookup failed")
    if reused is not None:
        out = reused.strategy
    else:
        result = await _llm(runtime, "strategy", strategy_prompt(brief, _now(runtime).date()), StrategyOut, _ctx(runtime, state))
        out = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    warnings = []
    if brief.ignored_countries:
        warnings.append(f"ignored unknown country codes: {', '.join(brief.ignored_countries)}")
    try:
        from app.db.database import AsyncSessionLocal

        async with (sf or AsyncSessionLocal)() as session:
            await session.merge(
                RunStrategy(
                    run_id=state["run_id"], campaign_id=state.get("campaign_id"),
                    brief_hash=f"{STRATEGY_PROMPT_VERSION}:{brief.hash()}", strategy=out,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("could not save run strategy")
    return {"strategy": out, "warnings": warnings}


async def platform_select(state: DiscoveryState, runtime: Runtime[Deps]) -> dict:
    brief = _brief(state)
    preset = K.PRESET_PLATFORMS[brief.founder_type]
    answers = None
    try:
        jb = brief.judge_brief()
        answers = await _judge(runtime, build_state(jb, {"platform": "any"}), platform_questions(jb, list(PLATFORMS)), _ctx(runtime, state))
    except Exception as exc:  # no Jev: fall back to the preset
        logger.warning("platform check failed, using preset: %s", exc)
    chosen = select_platforms(preset, answers, list(PLATFORMS))
    built = set(runtime.context.adapters)
    warnings = []
    for p, info in chosen.items():
        info["built"] = p in built
        info["mode"] = ("full" if p in preset else "probe") if info["selected"] and info["built"] else None
        if info["selected"] and not info["built"]:
            warnings.append(f"{p} isn't available yet, so it was skipped")
    return {"platforms": chosen, "warnings": warnings}


async def db_search(state: DiscoveryState, runtime: Runtime[Deps]) -> dict:
    """Creators we already know whose content is close to the brief. Free and instant."""
    brief = _brief(state)
    try:
        [query] = await _embed(runtime, [f"{brief.product} {brief.persona}"], "query", _ctx(runtime, state))
        hits = await repo.similar_creators(
            query,
            min_followers=brief.min_subscribers,
            max_followers=brief.max_subscribers,
            limit=L.DB_SEARCH_LIMIT,
            session_factory=runtime.context.session_factory,
        )
    except Exception as exc:
        return {"db_hits": [], "warnings": [f"creator database search skipped: {type(exc).__name__}"]}
    return {"db_hits": [{"creator_id": h.creator_id, "platform": h.platform, "platform_id": h.platform_id,
                         "similarity": h.similarity} for h in hits]}


# --- 2. fan out to platform branches ---------------------------------------------------------------------------


async def plan(state: DiscoveryState) -> dict:
    """Join point: waits for strategy, platform_select and db_search."""
    return {}


def fan_out(state: DiscoveryState) -> list[Send]:
    sends = []
    for p, info in (state.get("platforms") or {}).items():
        if info.get("mode"):
            sends.append(Send("platform_branch", {
                "run_id": state["run_id"], "brief": state["brief"], "strategy": state["strategy"],
                "platform": p, "mode": info["mode"],
                "db_hits": [h for h in state.get("db_hits") or [] if h["platform"] == p],
            }))
    return sends or [Send("merge_rank", state)]


# --- 3. inside a platform branch ---------------------------------------------------------------------------------


async def search(state: BranchState, runtime: Runtime[Deps]) -> dict:
    platform, mode = state["platform"], state["mode"]
    adapter = runtime.context.adapters[platform]()
    limits = L.LIMITS_BY_MODE[mode]
    brief = _brief(state)
    if brief.target_countries:
        limits = replace(limits, region=brief.target_countries[0])
    warnings = []
    try:
        refs = await adapter.source_candidates(_strategy_obj(state), limits)
    except Exception as exc:
        refs, warnings = [], [f"{platform} search failed: {type(exc).__name__}"]
    warnings += [f"{platform}: {w}" for w in getattr(adapter, "warnings", [])]
    seen = {r.platform_id for r in refs}
    out = [{"platform_id": r.platform_id, "found_via": r.found_via} for r in refs]
    for h in state.get("db_hits") or []:  # creators from our database get a fresh look too
        if h["platform_id"] not in seen:
            out.append({"platform_id": h["platform_id"], "found_via": "creator_db"})
    _emit({"type": "stage", "stage": f"{platform}: found {len(out)} candidates"})
    return {"refs": out, "warnings": warnings}


async def fetch_measure(state: BranchState, runtime: Runtime[Deps]) -> dict:
    """Fetch profiles + posts (cheap filter first), compute metrics, apply gates, save to the creator DB."""
    platform, brief = state["platform"], _brief(state)
    adapter = runtime.context.adapters[platform]()
    limits = L.LIMITS_BY_MODE[state["mode"]]
    via = {r["platform_id"]: r["found_via"] for r in state.get("refs") or []}
    todo = list(via) if state.get("fetch_ids") is None else state["fetch_ids"]
    if state.get("fetch_ids") is not None:
        limits = L.TOPUP_LIMITS
    refs = [CandidateRef(platform, pid, via[pid]) for pid in todo[: limits.max_profiles]]
    profiles = await adapter.fetch_profiles(refs, brief.constraints())
    sf, mctx, now = runtime.context.session_factory, brief.metrics_context(), _now(runtime)

    kept, rows = [], []
    for p in profiles:
        peers = None
        try:
            from app.metrics.stats import follower_tier

            peers = await repo.peer_engagement(platform, follower_tier(p.get("followers")), session_factory=sf)
        except Exception:
            pass
        m = compute_metrics(p, mctx, peer_engagement=peers, now=now)
        ok, why = passes_gates(m, mctx)
        cid = await repo.upsert_profile(p, session_factory=sf)
        await repo.save_snapshot(cid, p, m.to_dict(), session_factory=sf)
        rows.append(RunCandidate(run_id=state["run_id"], creator_id=cid, platform=platform, found_via=via.get(p["platform_id"]),
                                 mode=state["mode"], stage="measured" if ok else "filtered_out", metrics=m.to_dict(),
                                 drop_reason=None if ok else why))
        if ok:
            kept.append(cid)
    for pid, reason in getattr(adapter, "dropped", {}).items():
        rows.append(RunCandidate(run_id=state["run_id"], creator_id=f"{platform}:{pid}", platform=platform,
                                 found_via=via.get(pid), mode=state["mode"], stage="filtered_out", drop_reason=reason))
    await _save_rows(sf, rows)
    _emit({"type": "stage", "stage": f"{platform}: {len(kept)} of {len(profiles)} creators passed the checks"})
    before = state.get("stats") or {}
    measured = list(dict.fromkeys((state.get("measured") or []) + kept))  # a top-up round adds to the first
    stats = {k: before.get(k, 0) + v for k, v in {"sourced": len(refs), "fetched": len(profiles), "kept": len(kept)}.items()}
    return {"measured": measured, "stats": stats,
            "warnings": [f"{platform}: {w}" for w in getattr(adapter, "warnings", [])]}


def needs_top_up(state: BranchState) -> str:
    """After measuring: one extra search round when a full branch kept too few creators."""
    wanted = L.TOPUP_FACTOR * max(1, _brief(state).creator_count)
    if state["mode"] == "full" and not state.get("topped_up") and len(state.get("measured") or []) < wanted:
        return "top_up"
    return "shortlist"


async def top_up(state: BranchState, runtime: Runtime[Deps]) -> dict:
    """Second search round: unused queries first, all-time post search ordered by views.
    Only creators not already looked at are fetched."""
    platform = state["platform"]
    adapter = runtime.context.adapters[platform]()
    limits = replace(L.TOPUP_LIMITS, query_offset=L.LIMITS_BY_MODE[state["mode"]].max_queries)
    brief = _brief(state)
    if brief.target_countries:
        limits = replace(limits, region=brief.target_countries[0])
    warnings = []
    try:
        found = await adapter.source_candidates(_strategy_obj(state), limits)
    except Exception as exc:
        found, warnings = [], [f"{platform} extra search failed: {type(exc).__name__}"]
    warnings += [f"{platform}: {w}" for w in getattr(adapter, "warnings", [])]
    old = state.get("refs") or []
    seen = {r["platform_id"] for r in old}
    new = [{"platform_id": r.platform_id, "found_via": r.found_via} for r in found if r.platform_id not in seen]
    new = list({r["platform_id"]: r for r in new}.values())
    _emit({"type": "stage", "stage": f"{platform}: few creators passed, searched again and found {len(new)} more"})
    return {"refs": old + new, "fetch_ids": [r["platform_id"] for r in new], "topped_up": True, "warnings": warnings}


def after_top_up(state: BranchState) -> str:
    return "fetch_measure" if state.get("fetch_ids") else "shortlist"


async def shortlist(state: BranchState, runtime: Runtime[Deps]) -> dict:
    """Hybrid similarity (embeddings + keywords) to the brief; the top SHORTLIST_SIZE go to Jev."""
    ids = state.get("measured") or []
    if len(ids) <= L.SHORTLIST_SIZE:
        return {"shortlisted": ids}
    sf, ctx = runtime.context.session_factory, _ctx(runtime, state)
    profiles = await repo.get_creators(ids, session_factory=sf)
    order = [i for i in ids if i in profiles]
    texts = [_creator_text(profiles[i]) for i in order]
    query = _query_text(_brief(state), state["strategy"])

    vectors: list[Optional[list[float]]] = []
    for cid, text in zip(order, texts):
        vectors.append(await repo.get_embedding(cid, repo.text_hash(text), session_factory=sf))
    missing = [i for i, v in enumerate(vectors) if v is None]
    if missing:
        try:
            new = await _embed(runtime, [texts[i] for i in missing], "document", ctx)
            for i, v in zip(missing, new):
                vectors[i] = v
                await repo.save_embedding(order[i], v, repo.text_hash(texts[i]), session_factory=sf)
        except Exception as exc:
            logger.warning("embedding failed, shortlisting by keywords only: %s", exc)
    try:
        [qv] = await _embed(runtime, [query], "query", ctx)
    except Exception:
        qv = None

    bm25 = BM25Okapi([_tokens(t) or ["_"] for t in texts]).get_scores(_tokens(query))
    top_bm = max(bm25) if len(bm25) and max(bm25) > 0 else 1.0
    scored = []
    for i, cid in enumerate(order):
        sim = 0.0
        if qv is not None and vectors[i] is not None:
            a, b = np.asarray(vectors[i]), np.asarray(qv)
            sim = float(a @ b / ((np.linalg.norm(a) or 1) * (np.linalg.norm(b) or 1)))
        score = L.SHORTLIST_EMBED_WEIGHT * sim + (1 - L.SHORTLIST_EMBED_WEIGHT) * (bm25[i] / top_bm)
        scored.append((score, cid))
    scored.sort(reverse=True)
    return {"shortlisted": [cid for _, cid in scored[: L.SHORTLIST_SIZE]]}


async def judge_score(state: BranchState, runtime: Runtime[Deps]) -> dict:
    """Jev for every shortlisted creator (in parallel, cached), then scoring in code."""
    platform, brief = state["platform"], _brief(state)
    ids = state.get("shortlisted") or []
    if not ids:
        return {"branch_runs": [{"platform": platform, "mode": state["mode"], **(state.get("stats") or {}), "judged": 0}]}
    sf, ctx = runtime.context.session_factory, _ctx(runtime, state)
    strategy = state["strategy"]
    jb = brief.judge_brief(pain_points=strategy.get("pain_points"), trend_topics=strategy.get("trend_topics"),
                           safety_level=strategy.get("safety_level", "medium"))
    questions = creator_questions(jb, platform)
    bh = repo.brief_hash(jb)
    profiles = await repo.get_creators(ids, session_factory=sf)
    via = {r["platform_id"]: r["found_via"] for r in state.get("refs") or []}

    # 1. cached answers (database, one after another)
    judgments: dict[str, Judgment] = {}
    hashes: dict[str, str] = {}
    for cid in ids:
        p = profiles.get(cid)
        if not p:
            continue
        hashes[cid] = repo.content_hash(p)
        cached = await repo.get_cached_judgment(cid, hashes[cid], bh, K.QUESTIONS_VERSION, session_factory=sf)
        if cached:
            judgments[cid] = Judgment.from_dict(cached)

    # 2. Jev for the rest, in parallel (the client caps how many run at once)
    async def ask(cid: str):
        try:
            return cid, await _judge(runtime, build_state(jb, profiles[cid]), questions, ctx)
        except Exception as exc:
            logger.warning("judging failed for %s: %s", cid, exc)
            return cid, None

    fresh = [r for r in await asyncio.gather(*(ask(c) for c in hashes if c not in judgments))]

    # 3. save new answers (database, one after another)
    for cid, j in fresh:
        if j is not None:
            judgments[cid] = j
            await repo.save_judgment(cid, hashes[cid], bh, K.QUESTIONS_VERSION, j.to_dict(), session_factory=sf)

    results = []
    for cid, j in judgments.items():
        p = profiles[cid]
        s = score_creator(j, Metrics(**(p.get("metrics") or {})), exclude_kids_content=brief.exclude_kids_content)
        results.append({
            "creator_id": cid, "platform": platform, "platform_id": p["platform_id"],
            "display_name": p.get("display_name", ""), "found_via": via.get(p["platform_id"]), "mode": state["mode"],
            "final_score": s.final_score, "fit": s.fit, "health": s.health, "risk": s.risk,
            "deal_status": s.deal_status, "flags": s.flags, "dropped": s.dropped, "drop_reasons": s.drop_reasons,
            "signals": _signals(j),
        })
    if ids and not results:
        # Every judgment failed (Jev and its backup down): fail this step so the run is retried
        # and resumes here, instead of finishing with an empty list.
        raise JudgeStepError(f"{platform}: could not judge any of {len(ids)} creators")
    await _save_rows(sf, [
        RunCandidate(run_id=state["run_id"], creator_id=r["creator_id"], platform=platform, found_via=r["found_via"],
                     mode=r["mode"], stage="dropped" if r["dropped"] else "scored", fit=r["fit"], health=r["health"],
                     risk=r["risk"], final_score=r["final_score"], deal_status=r["deal_status"], flags=r["flags"],
                     drop_reason="; ".join(r["drop_reasons"]) or None, metrics=(profiles[r["creator_id"]].get("metrics")))
        for r in results
    ])
    live = sorted((r for r in results if not r["dropped"]), key=lambda r: -r["final_score"])
    _emit({"type": "leads", "platform": platform,
           "items": [{k: r[k] for k in ("creator_id", "display_name", "final_score", "deal_status", "flags")} for r in live]})
    failed = len(ids) - len(results)
    return {
        "candidates": {r["creator_id"]: r for r in results},
        "branch_runs": [{"platform": platform, "mode": state["mode"], **(state.get("stats") or {}), "judged": len(results)}],
        "warnings": [f"{platform}: {failed} creators couldn't be judged"] if failed else [],
    }


async def _save_rows(session_factory, rows: list[RunCandidate]) -> None:
    if not rows:
        return
    try:
        from app.db.database import AsyncSessionLocal

        async with (session_factory or AsyncSessionLocal)() as session:
            for r in rows:
                await session.merge(r)
            await session.commit()
    except Exception:
        logger.exception("could not save run candidates")


# --- 4. merge, probe check, reasons, finalize --------------------------------------------------------------------


def _ranked(state: DiscoveryState) -> list[dict]:
    live = [r for r in (state.get("candidates") or {}).values() if not r.get("dropped")]
    return sorted(live, key=lambda r: (-r["final_score"], r.get("display_name", "")))


async def merge_rank(state: DiscoveryState) -> dict:
    n = Brief(**state["brief"]).creator_count
    return {"top": [r["creator_id"] for r in _ranked(state)[:n]]}


def _expanded(state: DiscoveryState) -> set[str]:
    return {b["platform"] for b in state.get("branch_runs") or [] if b.get("mode") == "expand"}


def probe_check(state: DiscoveryState) -> list[Send]:
    """Expand a probed platform when one of its creators beats the current top-N cutoff, or when
    the top creators' fit is weak overall. Each platform is expanded at most once; the expansion
    branches run in parallel and come back to merge_rank."""
    ranked = _ranked(state)
    n = Brief(**state["brief"]).creator_count
    top = ranked[:n]
    cutoff = top[-1]["final_score"] if len(top) >= n else -1.0
    weak = (sum(r["fit"] for r in top) / len(top) < L.FIT_FLOOR) if top else True
    done = _expanded(state)
    sends = []
    for p, info in (state.get("platforms") or {}).items():
        if info.get("mode") != "probe" or p in done:
            continue
        probe_best = max((r["final_score"] for r in ranked if r["platform"] == p), default=-1.0)
        if probe_best > cutoff or weak:
            sends.append(Send("platform_branch", {
                "run_id": state["run_id"], "brief": state["brief"], "strategy": state["strategy"],
                "platform": p, "mode": "expand", "db_hits": [],
            }))
    if sends:
        return sends
    return [Send("reason", {"run_id": state["run_id"], "brief": state["brief"], "creator": r}) for r in top] or [
        Send("finalize", state)
    ]


async def reason(state: ReasonState, runtime: Runtime[Deps]) -> dict:
    """One "why this creator" sentence. Cached by creator content + brief + prompt version."""
    c, brief = state["creator"], Brief(**state["brief"])
    profiles = await repo.get_creators([c["creator_id"]], session_factory=runtime.context.session_factory)
    p = profiles.get(c["creator_id"]) or {}
    titles = [x.get("text", "") for x in (p.get("recent_posts") or [])]
    prompt = reason_prompt(brief, c.get("display_name", ""), titles, c.get("signals") or {}, c.get("deal_status"))

    async def compute():
        out = await _llm(runtime, "brief", prompt, ReasonOut, _ctx(runtime, state))
        return out.reasoning if hasattr(out, "reasoning") else str(out)

    try:
        from app.discovery.cache import cached

        text, _ = await cached("llm", {"v": REASON_PROMPT_VERSION, "creator": repo.content_hash(p), "brief": brief.hash(),
                                "verdict": c.get("deal_status")},
                               None, compute, session_factory=runtime.context.session_factory)
    except Exception as exc:
        logger.warning("reason failed for %s: %s", c["creator_id"], exc)
        text = ""
    return {"reasons": {c["creator_id"]: text}}


async def finalize(state: DiscoveryState, runtime: Runtime[Deps]) -> dict:
    brief = Brief(**state["brief"])
    ranked = _ranked(state)[: L.FINAL_LIST_MAX]
    profiles = await repo.get_creators([r["creator_id"] for r in ranked], session_factory=runtime.context.session_factory)
    reasons = state.get("reasons") or {}
    leads = [
        to_legacy_lead(profiles[r["creator_id"]], profiles[r["creator_id"]].get("metrics") or {}, r,
                       reasons.get(r["creator_id"]), brief.industry)
        for r in ranked if r["creator_id"] in profiles
    ]
    return {"final_leads": leads}
