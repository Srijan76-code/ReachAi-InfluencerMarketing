"""Run (or resume) the discovery graph for one campaign run (spec §4.14).

- One LangGraph thread per run. If the thread already has a checkpoint with steps left
  (an Inngest retry after a crash or timeout), resume with `None` instead of starting over.
- durability="sync": each step's checkpoint is saved before the next starts.
- Progress and newly scored creators are published live; the campaign row is updated.
- Errors are re-raised so Inngest retries (and the retry resumes). The campaign is marked
  failed only by the function's on_failure handler, after the last retry.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from inngest.experimental.realtime import publish as publish_realtime
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import update

from app.billing.costs import CostContext
from app.core.config import LANGGRAPH_CHECKPOINTER_URL
from app.discovery.brief import parse_brief
from app.discovery.graph import build_discovery_graph
from app.discovery.node_cache import PostgresNodeCache
from app.discovery.state import Deps

logger = logging.getLogger(__name__)

STAGE_LABELS = {
    "strategy": "Understanding the brief",
    "platform_select": "Choosing platforms",
    "db_search": "Checking creators we already know",
    "plan": "Planning the search",
    "search": "Searching for creators",
    "fetch_measure": "Measuring creators",
    "top_up": "Searching again for more creators",
    "shortlist": "Shortlisting the closest matches",
    "judge_score": "Judging fit and risk",
    "merge_rank": "Ranking creators",
    "reason": "Writing why each creator fits",
    "finalize": "Finishing up",
}


def thread_for(run_id: str) -> str:
    return f"discovery-{run_id}"


def default_deps(ctx: CostContext) -> Deps:
    from app.discovery.cache import cached
    from app.platforms.youtube import YouTubeAdapter
    from app.platforms.youtube_api import HttpYouTubeAPI

    shared: dict[str, Any] = {}
    deps = Deps(adapters={}, cost_context=ctx, extra=shared)

    async def run_cache(namespace, key, ttl, compute):
        # Read at call time: run_discovery sets deps.session_factory after this is built, and the
        # adapter's search cache must use the same database as the rest of the run.
        return await cached(namespace, key, ttl, compute, session_factory=deps.session_factory)

    def youtube():
        if "api" not in shared:
            shared["api"] = HttpYouTubeAPI(context=ctx)
        return YouTubeAdapter(shared["api"], cache=run_cache)

    deps.adapters = {"youtube": youtube}

    from app.core import config

    if config.X_ENABLED and os.getenv("X_PROVIDER_API_KEY"):
        from app.platforms.x import XAdapter
        from app.platforms.x_api import HttpXAPI

        def x():
            if "x_api" not in shared:
                shared["x_api"] = HttpXAPI(context=ctx)
            return XAdapter(shared["x_api"], cache=run_cache)

        deps.adapters["x"] = x

    if config.INSTAGRAM_ENABLED and (os.getenv("APIFY_TOKEN") or os.getenv("APIFY_API_TOKEN")):
        from app.platforms.apify import HttpApify, db_memo
        from app.platforms.instagram import DbStore, InstagramAdapter

        def instagram():
            if "apify" not in shared:
                shared["apify"] = HttpApify(context=ctx, memo=db_memo(lambda: deps.session_factory))
            return InstagramAdapter(shared["apify"], store=DbStore(lambda: deps.session_factory))

        deps.adapters["instagram"] = instagram
    return deps


async def _publish(run_id: str, topic: str, data: dict) -> None:
    try:
        from app.inngest.client import inngest_client

        await publish_realtime(inngest_client, channel=f"campaign:{run_id}", topic=topic,
                               data={"run_id": run_id, "ts": int(time.time() * 1000), **data})
    except Exception:
        logger.exception("realtime publish failed (%s)", topic)


async def _set_campaign(campaign_id: str, session_factory=None, **values) -> None:
    from app.db.database import AsyncSessionLocal
    from app.models.campaign import Campaign

    async with (session_factory or AsyncSessionLocal)() as db:
        await db.execute(update(Campaign).where(Campaign.campaign_id == campaign_id).values(**values))
        await db.commit()


async def run_discovery(
    *,
    campaign_id: str,
    run_id: str,
    campaign_details: dict,
    user_id: Optional[str] = None,
    deps: Optional[Deps] = None,
    checkpointer=None,
    session_factory=None,
    publish=None,
) -> dict:
    """Returns {"leads": [...], "warnings": [...], "resumed": bool}."""
    from app.models.campaign import CampaignStatus

    ctx = CostContext(user_id=user_id, campaign_id=campaign_id, run_id=run_id)
    deps = default_deps(ctx) if deps is None else deps
    deps.session_factory = deps.session_factory or session_factory
    publish = _publish if publish is None else publish
    thread_id = thread_for(run_id)
    cfg = {"configurable": {"thread_id": thread_id}}

    async def body(saver):
        graph = build_discovery_graph().compile(
            checkpointer=saver, cache=PostgresNodeCache(session_factory=deps.session_factory)
        )
        snapshot = await graph.aget_state(cfg)
        resumed = bool(snapshot and snapshot.next)
        start = None if resumed else {
            "run_id": run_id, "campaign_id": campaign_id, "brief": parse_brief(campaign_details).to_dict(),
        }
        if resumed:
            logger.info("Resuming discovery run %s at %s", run_id, snapshot.next)
        last_stage = None
        async for _ns, mode, chunk in graph.astream(start, cfg, context=deps, stream_mode=["updates", "custom"],
                                                     subgraphs=True, durability="sync"):
            if mode == "custom":
                if chunk.get("type") == "leads":
                    await publish(run_id, "leads", {"platform": chunk.get("platform"), "items": chunk.get("items", [])})
                elif chunk.get("type") == "stage":
                    await publish(run_id, "status", {"thread_id": thread_id, "stage": chunk["stage"], "status": "running"})
                continue
            for node in chunk or {}:
                label = STAGE_LABELS.get(node)
                if label and label != last_stage:
                    last_stage = label
                    await publish(run_id, "status", {"thread_id": thread_id, "stage": label, "status": "running"})
                    await _set_campaign(campaign_id, deps.session_factory, current_stage=label, workflow_status={
                        "run_id": run_id, "thread_id": thread_id, "stage": label, "status": "running"})
        final = (await graph.aget_state(cfg)).values
        return final, resumed

    if checkpointer is not None:
        final, resumed = await body(checkpointer)
    else:
        async with AsyncPostgresSaver.from_conn_string(LANGGRAPH_CHECKPOINTER_URL) as saver:
            await saver.setup()
            final, resumed = await body(saver)

    leads = final.get("final_leads") or []
    warnings = final.get("warnings") or []
    await _set_campaign(
        campaign_id, deps.session_factory, campaign_leads=leads, status=CampaignStatus.COMPLETED, thread_id=thread_id,
        current_stage="completed",
        workflow_status={"run_id": run_id, "thread_id": thread_id, "stage": "completed", "status": "completed",
                         "warnings": warnings, "engine": "graph"},
    )
    await _settle_credits(run_id, len(leads), deps.session_factory)
    await publish(run_id, "status", {"thread_id": thread_id, "stage": "completed", "status": "completed"})
    for key in ("api", "x_api", "apify"):
        client = (deps.extra or {}).get(key)
        if client is not None and hasattr(client, "aclose"):
            await client.aclose()
    return {"leads": leads, "warnings": warnings, "resumed": resumed}


async def _settle_credits(run_id: str, creators_found: int, session_factory=None, failed: bool = False) -> None:
    """Keep, refund or release the search's credits (spec §5.3). Never fails the run: a reservation left
    held is released by the hourly sweep, in the user's favour."""
    from app.billing import ledger
    from app.db.database import AsyncSessionLocal

    try:
        async with (session_factory or AsyncSessionLocal)() as db:
            if failed:
                await ledger.release(db, run_id)
            else:
                await ledger.settle(db, run_id, creators_found)
            await db.commit()
    except Exception:
        logger.exception("Could not settle credits for run %s", run_id)


async def mark_failed(*, campaign_id: str, run_id: str, error: str, session_factory=None, publish=None) -> None:
    """Called once, after the last retry (Inngest on_failure)."""
    from app.models.campaign import CampaignStatus

    publish = _publish if publish is None else publish
    await _set_campaign(campaign_id, session_factory, status=CampaignStatus.CREATED, current_stage="failed",
                        workflow_status={"run_id": run_id, "thread_id": thread_for(run_id), "stage": "failed",
                                         "status": "failed", "error": error[:500]})
    await _settle_credits(run_id, 0, session_factory, failed=True)
    await publish(run_id, "status", {"thread_id": thread_for(run_id), "stage": "failed", "status": "failed"})
