"""Starting a creator search. Shared by the web route and the MCP tools so both behave the same."""

import logging
from uuid import uuid4

import inngest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.campaign_names import DEFAULT_NAME, is_default, name_from_brief
from app.inngest.client import inngest_client
from app.models.campaign import Campaign, CampaignStatus

logger = logging.getLogger(__name__)


class EnqueueError(Exception):
    """The search was recorded but could not be queued."""


async def start_run(db: AsyncSession, campaign: Campaign, details: dict, clerk_id: str) -> dict:
    """Mark the campaign as running and queue the Inngest search. Returns the ids to poll with."""
    campaign_id = campaign.campaign_id
    thread_id = campaign.thread_id or f"campaign-{campaign_id}"
    run_id = str(uuid4())

    await db.execute(
        update(Campaign)
        .where(Campaign.campaign_id == campaign_id)
        .values(
            # name it from the brief unless the user already named it
            name=(name_from_brief(details) or DEFAULT_NAME) if is_default(campaign.name) else campaign.name,
            campaign_details=details,
            run_id=run_id,
            thread_id=thread_id,
            status=CampaignStatus.PENDING,
            workflow_status={
                "run_id": run_id,
                "thread_id": thread_id,
                "stage": "queued",
                "status": "running",
            },
        )
    )
    await db.commit()

    try:
        await inngest_client.send(
            inngest.Event(
                name="campaign/run",
                data={
                    "campaign_id": campaign_id,
                    "campaign_details": details,
                    "user_id": clerk_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                },
            )
        )
        logger.info(f"[Inngest] Sent campaign/run event for {campaign_id}")
    except Exception as inngest_err:
        logger.exception("[Inngest] Failed to enqueue campaign %s", campaign_id)
        raise EnqueueError(str(inngest_err)) from inngest_err

    return {"success": True, "campaign_id": campaign_id, "run_id": run_id, "thread_id": thread_id}
