import logging
import time
from typing import Any

from inngest.experimental.realtime import publish as publish_realtime
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select

from app.core.config import LANGGRAPH_CHECKPOINTER_URL
from app.db.database import AsyncSessionLocal
from app.inngest.client import inngest_client
from app.models.campaign import Campaign
from app.models.outreach import OutreachJob, OutreachPitch
from app.outreach.graph import build_outreach_graph

logger = logging.getLogger(__name__)


async def _publish(job_id: str, run_id: str | None, stage: str, status: str = "running", **extra: Any) -> None:
    if not run_id:
        return
    try:
        await publish_realtime(
            inngest_client,
            channel=f"outreach:{run_id}",
            topic="status",
            data={"outreach_job_id": job_id, "stage": stage, "status": status, "ts": int(time.time() * 1000), **extra},
        )
    except Exception:
        logger.exception("Unable to publish outreach status for %s", job_id)


async def run_outreach_graph(outreach_job_id: str, run_id: str, thread_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        job_result = await db.execute(select(OutreachJob).where(OutreachJob.outreach_job_id == outreach_job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            raise ValueError("Outreach job not found")

        campaign_result = await db.execute(select(Campaign).where(Campaign.campaign_id == job.campaign_id))
        campaign = campaign_result.scalar_one_or_none()
        if not campaign:
            raise ValueError("Campaign not found")

        leads_by_id = {
            str(creator.get("id") or creator.get("creator_id")): creator
            for creator in (campaign.campaign_leads or [])
        }
        selected_creators = [
            leads_by_id[creator_id]
            for creator_id in (job.selected_creator_ids or [])
            if creator_id in leads_by_id
        ]
        if not selected_creators:
            raise ValueError("Selected creators are no longer available in the campaign")
        initial_state = {
            "outreach_job_id": job.outreach_job_id,
            "campaign_id": job.campaign_id,
            "campaign_context": campaign.campaign_details or {},
            "selected_creators": selected_creators,
            "default_collaboration": {"type": job.collaboration_type},
            "default_deliverables": job.deliverables or [],
            "creator_overrides": job.creator_overrides or {},
            "model_name": "gemini-3.8-flash",
        }
        config = {"configurable": {"thread_id": thread_id}, "max_concurrency": 5}
        await _publish(outreach_job_id, run_id, "prepare_pitch_batch")
        try:
            async with AsyncPostgresSaver.from_conn_string(LANGGRAPH_CHECKPOINTER_URL) as checkpointer:
                await checkpointer.setup()
                workflow = build_outreach_graph().compile(
                    checkpointer=checkpointer,
                    cache=InMemoryCache(),
                )
                completed_creators: set[str] = set()
                total_creators = len(selected_creators)

                async for event in workflow.astream_events(initial_state, config=config, version="v2"):
                    kind = event.get("event")
                    node_name = (event.get("metadata") or {}).get("langgraph_node")
                    if not node_name:
                        continue

                    if kind == "on_chain_start":
                        creator_id = None
                        inp = (event.get("data") or {}).get("input")
                        if isinstance(inp, dict):
                            creator_id = (inp.get("creator_input") or {}).get("creator_id")
                        await _publish(
                            outreach_job_id,
                            run_id,
                            str(node_name),
                            creator_id=creator_id,
                            status="running",
                            completed_count=len(completed_creators),
                            total_count=total_creators,
                        )
                    elif kind == "on_chain_end" and node_name == "collect_creator_pitch":
                        out = (event.get("data") or {}).get("output") or {}
                        pitch_results = out.get("pitch_results") or []
                        for res in pitch_results:
                            cid = res.get("creator_id")
                            if cid:
                                completed_creators.add(cid)
                            await _publish(
                                outreach_job_id,
                                run_id,
                                "creator_pitch_completed",
                                creator_id=cid,
                                pitch_status=res.get("status"),
                                status="running",
                                completed_count=len(completed_creators),
                                total_count=total_creators,
                            )
                state_snapshot = await workflow.aget_state(config)
                final_state = state_snapshot.values if hasattr(state_snapshot, "values") else {}

            pitch_pack = final_state.get("pitch_pack") or {}
            stats = final_state.get("generation_stats") or {}
            results_by_creator = {
                item.get("creator_id"): item
                for item in final_state.get("pitch_results") or []
            }
            pitch_rows = await db.execute(
                select(OutreachPitch).where(OutreachPitch.outreach_job_id == outreach_job_id)
            )
            for pitch in pitch_rows.scalars().all():
                result = results_by_creator.get(pitch.creator_id) or {}
                pitch.status = result.get("status", "needs_review").upper()
                pitch.pitch_bundle = result.get("pitch_bundle") or {}
                pitch.validation_errors = result.get("validation_errors") or []
                pitch.repair_count = result.get("repair_count", 0)

            job.status = "COMPLETED"
            job.pitch_pack = pitch_pack
            job.generation_stats = stats
            job.run_id = run_id
            job.thread_id = thread_id
            await db.commit()
            await _publish(outreach_job_id, run_id, "completed", status="completed", stats=stats)
            return {
                "success": True,
                "outreach_job_id": outreach_job_id,
                "run_id": run_id,
                "thread_id": thread_id,
                "stats": stats,
            }
        except Exception as exc:
            logger.exception("Outreach job %s failed", outreach_job_id)
            job.status = "FAILED"
            job.error_message = str(exc)
            await db.commit()
            await _publish(outreach_job_id, run_id, "failed", status="failed", error=str(exc))
            raise