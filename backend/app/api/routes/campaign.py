import asyncio
import json
import logging
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from sqlalchemy import Text, case, cast, desc, func, or_, select, update
from sqlalchemy.orm import load_only

from app.db.database import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.campaign import Campaign, CampaignStatus
from app.auth.user import get_db_user
from app.inngest.client import inngest_client
from app.api.campaign_runs import EnqueueError, start_run
from app.api.campaign_names import EMPTY_DRAFT_HIDDEN_AFTER_DAYS, DEFAULT_NAME, clean_name, is_default, name_from_brief
from pydantic import BaseModel
import inngest

logger = logging.getLogger(__name__)

router = APIRouter()


# GET /api/campaigns
@router.get("/")
async def get_campaigns(
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    # Only the columns the list shows; leads are counted inside Postgres, so a campaign's full results
    # (often 50-100 KB of JSON each) are never transferred or parsed just to show a number.
    # campaign_leads can be SQL NULL or JSON null (a campaign with no results yet): count arrays only.
    leads_count = case((func.jsonb_typeof(Campaign.campaign_leads) == "array",
                        func.jsonb_array_length(Campaign.campaign_leads)), else_=0).label("leads_count")
    result = await db.execute(
        select(Campaign.campaign_id, Campaign.name, Campaign.status, Campaign.current_stage, Campaign.stage_index,
               Campaign.campaign_details, Campaign.created_at, Campaign.updated_at, leads_count,
               Campaign.workflow_status["status"].astext.label("run_status"))
        .where(Campaign.user_id == user.user_id,
               # a draft whose brief was never run holds nothing (the brief is saved on run): after a
               # day it's just clutter from clicking "New campaign" and leaving
               or_(Campaign.campaign_details.isnot(None),
                   Campaign.created_at > func.now() - timedelta(days=EMPTY_DRAFT_HIDDEN_AFTER_DAYS)))
        .order_by(desc(Campaign.created_at))
    )
    return [
        {
            "id": c.campaign_id,
            # older campaigns kept the placeholder: show the name their brief would get
            "name": (name_from_brief(c.campaign_details) if is_default(c.name) else c.name) or DEFAULT_NAME,
            "run_status": c.run_status,  # running | completed | failed (None before the first run)
            "status": c.status.value.lower() if hasattr(c.status, "value") else str(c.status).lower(),
            "current_stage": c.current_stage,
            "stage_index": c.stage_index,
            "campaign_details": c.campaign_details,
            "leads_count": c.leads_count,
            "createdAt": c.created_at.isoformat() if c.created_at else None,
            "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in result.all()
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
        user_id=user.user_id,
        name=DEFAULT_NAME,
        status=CampaignStatus.CREATED,
        current_stage="Draft"
    )

    db.add(campaign)
    await db.commit()

    return {
        "success": True,
        "campaign_id": campaign.campaign_id
    }


class RenameBody(BaseModel):
    name: str


# PATCH /api/campaigns/{campaign_id}
@router.patch("/{campaign_id}")
async def rename_campaign(
    campaign_id: str,
    body: RenameBody,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    name = clean_name(body.name)
    if not name:
        raise HTTPException(422, "Name can't be empty")
    result = await db.execute(
        update(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id).values(name=name)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Campaign not found")
    await db.commit()
    return {"id": campaign_id, "name": name}


# DELETE /api/campaigns/{campaign_id}
@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    """Deletes the campaign with its saved creators and outreach (database cascades). A running search
    can't be deleted: its worker would write results into a campaign that no longer exists."""
    from sqlalchemy import delete

    row = (await db.execute(
        select(Campaign.status, Campaign.workflow_status["status"].astext)
        .where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Campaign not found")
    if row[0] == CampaignStatus.PENDING and row[1] == "running":
        raise HTTPException(409, "This campaign's search is still running. Delete it once it finishes.")
    await db.execute(delete(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id))
    await db.commit()
    return {"deleted": campaign_id}


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
            Campaign.user_id == user.user_id
        ).options(load_only(Campaign.campaign_id, Campaign.name, Campaign.status, Campaign.current_stage,
                            Campaign.stage_index, Campaign.campaign_details, Campaign.created_at, Campaign.run_id,
                            Campaign.thread_id, Campaign.workflow_status))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    return {
        "id": campaign.campaign_id,
        "name": (name_from_brief(campaign.campaign_details) if is_default(campaign.name) else campaign.name) or DEFAULT_NAME,
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
    campaign_details: dict | None = None,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.user_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    details = campaign_details if campaign_details is not None else (campaign.campaign_details or {})
    try:
        return await start_run(db, campaign, details, user.clerk_id)
    except EnqueueError as err:
        raise HTTPException(503, "Unable to enqueue campaign workflow") from err


@router.get("/{campaign_id}/status")
async def get_campaign_status(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.user_id
        ).options(load_only(Campaign.campaign_id, Campaign.name, Campaign.status, Campaign.current_stage,
                            Campaign.stage_index, Campaign.campaign_details, Campaign.created_at, Campaign.run_id,
                            Campaign.thread_id, Campaign.workflow_status))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    state = campaign.workflow_status or {
        "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
        "stage": None,
    }
    return {
        "campaign_id": campaign_id,
        "run_id": campaign.run_id,
        "thread_id": campaign.thread_id,
        "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
        "current_stage": state.get("stage"),
        "workflow_status": state,
    }


# GET /api/campaigns/{campaign_id}/leads
@router.get("/{campaign_id}/leads")
async def get_campaign_leads(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    # The leads list is the biggest payload in the app. Postgres returns it as JSON text and it goes
    # straight into the response: no decode into Python objects and re-encode on every page load.
    result = await db.execute(
        select(Campaign.status, Campaign.current_stage, Campaign.stage_index, Campaign.campaign_details,
               Campaign.name, cast(Campaign.campaign_leads, Text).label("leads_json"))
        .where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(404, "Campaign not found")

    head = json.dumps({
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "current_stage": row.current_stage,
        "stage_index": row.stage_index,
        "campaign_details": row.campaign_details,
        "name": row.name,
        "error": None,
    }, default=str)
    body = head[:-1] + ', "result": ' + (row.leads_json or "null") + "}"
    return Response(content=body, media_type="application/json")


# GET /api/campaigns/{campaign_id}/skipped
@router.get("/{campaign_id}/skipped")
async def get_campaign_skipped(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    """How many creators the run looked at and why the rest were left out, in plain buckets."""
    from app.discovery.skipped import summarise
    from app.models.discovery_run import RunCandidate

    run_id = (await db.execute(
        select(Campaign.run_id).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )).one_or_none()
    if run_id is None:
        raise HTTPException(404, "Campaign not found")
    if not run_id[0]:
        return summarise([])
    rows = (await db.execute(
        select(RunCandidate.stage, RunCandidate.drop_reason).where(RunCandidate.run_id == run_id[0])
    )).all()
    return summarise(rows)


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
                        Campaign.user_id == user.user_id
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