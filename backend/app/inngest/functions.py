import datetime
import logging

import inngest

from app.creators import constants as CREATOR
from app.discovery import limits as L
from app.inngest.client import inngest_client
from app.outreach.runtime import run_outreach_graph

logger = logging.getLogger(__name__)

async def _campaign_run_failed(ctx: inngest.Context):
    """Runs once, after the last retry of run_campaign: mark the campaign failed."""
    original = (ctx.event.data or {}).get("event", {}).get("data", {})
    error = (ctx.event.data or {}).get("error", {})
    if original.get("campaign_id") and original.get("run_id"):
        from app.discovery.runtime import mark_failed

        await mark_failed(campaign_id=original["campaign_id"], run_id=original["run_id"],
                          error=str(error.get("message") or error)[:500])


@inngest_client.create_function(
    fn_id="run_campaign",
    trigger=inngest.TriggerEvent(event="campaign/run"),
    retries=L.RUN_RETRIES,  # each retry resumes the LangGraph checkpoint
    concurrency=[
        inngest.Concurrency(key="event.data.user_id", limit=L.RUNS_PER_USER),
        inngest.Concurrency(limit=L.RUNS_PER_ACCOUNT),
    ],
    # a re-run of the same campaign cancels the run still going
    singleton=inngest.Singleton(key="event.data.campaign_id", mode="cancel"),
    idempotency="event.data.run_id",  # a repeated event for the same run doesn't start it twice
    cancel=[inngest.Cancel(event="campaign/cancel", if_exp="event.data.campaign_id == async.data.campaign_id")],
    timeouts=inngest.Timeouts(finish=datetime.timedelta(minutes=L.RUN_TIMEOUT_MINUTES)),
    on_failure=_campaign_run_failed,
)
async def run_campaign(ctx: inngest.Context):
    campaign_id = ctx.event.data["campaign_id"]
    campaign_details = ctx.event.data["campaign_details"]
    user_id = ctx.event.data.get("user_id")
    run_id = ctx.event.data["run_id"]

    from app.discovery.runtime import run_discovery

    # No try/except here: errors go back to Inngest, which retries, and the retry resumes from the
    # last checkpoint. on_failure marks the campaign failed after the last retry.
    result = await run_discovery(campaign_id=campaign_id, run_id=run_id,
                                 campaign_details=campaign_details, user_id=user_id)
    return {"success": True, "campaign_id": campaign_id, "run_id": run_id,
            "leads": len(result["leads"]), "resumed": result["resumed"], "warnings": result["warnings"]}


@inngest_client.create_function(
    fn_id="run_outreach",
    trigger=inngest.TriggerEvent(event="outreach/run"),
)
async def run_outreach(ctx: inngest.Context):
    data = ctx.event.data
    return await run_outreach_graph(
        outreach_job_id=data["outreach_job_id"],
        run_id=data["run_id"],
        thread_id=data["thread_id"],
    )


@inngest_client.create_function(
    fn_id="refresh_youtube_data",
    trigger=inngest.TriggerCron(cron=CREATOR.REFRESH_CRON),
    concurrency=[inngest.Concurrency(limit=1)],  # never two refreshes at once
    retries=2,
)
async def refresh_youtube_data(ctx: inngest.Context):
    """YouTube API policy: refresh or delete stored data after 30 days (spec §4.4)."""
    from app.creators.refresh import run_refresh
    from app.platforms.youtube import YouTubeAdapter
    from app.platforms.youtube_api import HttpYouTubeAPI
    from app.billing.costs import CostContext

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from app.core.config import LANGGRAPH_CHECKPOINTER_URL
    from app.creators.refresh import purge_old_checkpoints

    api = HttpYouTubeAPI(context=CostContext(run_id=f"refresh-{ctx.run_id}"))
    try:
        report = await run_refresh(adapter_factory=lambda: YouTubeAdapter(api))
    finally:
        await api.aclose()
    async with AsyncPostgresSaver.from_conn_string(LANGGRAPH_CHECKPOINTER_URL) as saver:
        await saver.setup()
        report.checkpoint_threads_deleted = await purge_old_checkpoints(saver)
    return report.to_dict()
