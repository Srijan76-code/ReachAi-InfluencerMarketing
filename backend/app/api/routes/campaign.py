import asyncio
import json
import logging
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc

from app.db.database import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.campaign import Campaign, CampaignStatus
from app.auth.user import get_db_user
from app.workflow.runtime import get_durable_checkpoint_status
from app.inngest.client import inngest_client
from app.inngest.functions import execute_campaign_workflow
import inngest

logger = logging.getLogger(__name__)

router = APIRouter()


# GET /api/campaigns
@router.get("/")
async def get_campaigns(
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign)
        .where(Campaign.user_id == user.clerk_id)
        .order_by(desc(Campaign.created_at))
    )
    campaigns = result.scalars().all()
    return [
        {
            "id": c.campaign_id,
            "name": c.name or "Untitled Campaign",
            "status": c.status.value.lower() if hasattr(c.status, "value") else str(c.status).lower(),
            "current_stage": c.current_stage,
            "stage_index": c.stage_index,
            "campaign_details": c.campaign_details,
            "leads_count": len(c.campaign_leads) if c.campaign_leads else 0,
            "createdAt": c.created_at.isoformat() if c.created_at else None,
            "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in campaigns
    ]


# POST /api/campaigns/create
@router.post("/create")
async def create_campaign(
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    new_id = str(uuid4())
    campaign = Campaign(
        campaign_id=new_id,
        user_id=user.clerk_id,
        name="Untitled Campaign",
        status=CampaignStatus.CREATED,
        current_stage="Draft"
    )

    db.add(campaign)
    await db.commit()

    return {
        "success": True,
        "campaign_id": campaign.campaign_id
    }


# GET /api/campaigns/{campaign_id}/details
@router.get("/{campaign_id}/details")
async def get_campaign_details(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.clerk_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    return {
        "id": campaign.campaign_id,
        "name": campaign.name or "Untitled Campaign",
        "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
        "current_stage": campaign.current_stage,
        "stage_index": campaign.stage_index,
        "campaign_details": campaign.campaign_details,
        "createdAt": campaign.created_at.isoformat() if campaign.created_at else None,
    }


# POST /api/campaigns/{campaign_id}/generate
@router.post("/{campaign_id}/generate")
async def generate_campaign(
    campaign_id: str,
    campaign_details: dict,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.clerk_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    thread_id = campaign.thread_id or f"campaign-{campaign_id}"
    run_id = campaign.run_id or str(uuid4())

    await db.execute(
        update(Campaign)
        .where(Campaign.campaign_id == campaign_id)
        .values(
            name=campaign_name,
            campaign_details=campaign_details,
            run_id=run_id,
            thread_id=thread_id,
            status=CampaignStatus.PENDING,
            workflow_status={
                "run_id": None,
                "thread_id": thread_id,
                "stage": "queued",
                "status": "running",
            },
        )
    )
    await db.commit()

    await inngest_client.send(
        inngest.Event(
            name="campaign/run",
            data={
                "campaign_id": campaign_id,
                "campaign_details": campaign_details,
                "user_id": user.clerk_id,
                "run_id": run_id,
                "thread_id": thread_id,
            }
        )
        logger.info(f"[Inngest] Sent campaign/run event for {campaign_id}")
    except Exception as inngest_err:
        logger.warning(f"[Inngest] Event send warning: {inngest_err}")

    # 2. Local background execution safeguard in case Inngest dev server is not actively attached
    asyncio.create_task(execute_campaign_workflow(campaign_id, campaign_details))

    return {
        "success": True,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "thread_id": thread_id,
    }


@router.get("/{campaign_id}/status")
async def get_campaign_status(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.clerk_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    state = campaign.workflow_status or {
        "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
        "stage": None,
    }
    checkpoint = await get_durable_checkpoint_status(campaign.thread_id)
    return {
        "campaign_id": campaign_id,
        "run_id": campaign.run_id,
        "thread_id": campaign.thread_id,
        "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
        "current_stage": state.get("stage"),
        "workflow_status": state,
        "durable_checkpoint": checkpoint,
    }


# GET /api/campaigns/{campaign_id}/leads
@router.get("/{campaign_id}/leads")
async def get_campaign_leads(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.clerk_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    return {
        "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
        "current_stage": campaign.current_stage,
        "stage_index": campaign.stage_index,
        "result": campaign.campaign_leads,
        "campaign_details": campaign.campaign_details,
        "name": campaign.name,
        "error": None
    }


# GET /api/campaigns/{campaign_id}/stream
@router.get("/{campaign_id}/stream")
async def stream_campaign_progress(
    campaign_id: str,
    request: Request,
    user: User = Depends(get_db_user)
):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Streams real-time stage updates while Inngest/LangGraph executes,
    and returns final leads on completion with zero polling required.
    """
    async def event_generator():
        last_stage = None
        last_index = None

        while True:
            if await request.is_disconnected():
                break

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Campaign).where(
                        Campaign.campaign_id == campaign_id,
                        Campaign.user_id == user.clerk_id
                    )
                )
                camp = result.scalar_one_or_none()

            if not camp:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Campaign not found'})}\n\n"
                break

            status_str = camp.status.value if hasattr(camp.status, "value") else str(camp.status)

            if status_str == "COMPLETED":
                yield f"data: {json.dumps({'type': 'complete', 'status': 'COMPLETED', 'leads': camp.campaign_leads or []})}\n\n"
                break

            # If stage has updated, emit stage event
            if camp.current_stage != last_stage or camp.stage_index != last_index:
                last_stage = camp.current_stage
                last_index = camp.stage_index
                yield f"data: {json.dumps({'type': 'stage', 'status': status_str, 'stage': camp.current_stage, 'stage_index': camp.stage_index})}\n\n"
            else:
                # Keep-alive ping
                yield f": keep-alive\n\n"

            await asyncio.sleep(0.7)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )