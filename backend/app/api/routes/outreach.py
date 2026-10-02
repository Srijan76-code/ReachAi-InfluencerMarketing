import uuid

import inngest
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.user import get_db_user
from app.db.database import get_db
from app.inngest.client import inngest_client
from app.models.campaign import Campaign
from app.models.outreach import OutreachJob, OutreachPitch
from app.models.user import User
from app.outreach.utils import available_channels
from app.schemas.outreach import OutreachJobCreate, OutreachJobDetailResponse, OutreachJobResponse


router = APIRouter()


def _creator_id(creator: dict) -> str:
    return str(creator.get("id") or creator.get("creator_id") or "")


def _job_response(job: OutreachJob) -> OutreachJobResponse:
    return OutreachJobResponse(
        outreach_job_id=job.outreach_job_id,
        campaign_id=job.campaign_id,
        status=job.status,
        run_id=job.run_id,
        thread_id=job.thread_id,
    )


@router.post("/campaigns/{campaign_id}/jobs", response_model=OutreachJobResponse, status_code=201)
async def create_outreach_job(
    campaign_id: str,
    payload: OutreachJobCreate,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.campaign_leads:
        raise HTTPException(400, "Campaign has no generated creator leads")
    if not payload.selected_creator_ids:
        raise HTTPException(400, "At least one creator must be selected")

    leads_by_id = {_creator_id(creator): creator for creator in campaign.campaign_leads}
    missing = [creator_id for creator_id in payload.selected_creator_ids if creator_id not in leads_by_id]
    if missing:
        raise HTTPException(400, {"unknown_creator_ids": missing})

    outreach_job_id = str(uuid.uuid4())
    job = OutreachJob(
        outreach_job_id=outreach_job_id,
        campaign_id=campaign_id,
        user_id=user.user_id,
        run_id=str(uuid.uuid4()),
        thread_id=outreach_job_id,
        status="PENDING" if payload.auto_start else "CREATED",
        collaboration_type=payload.collaboration_type,
        deliverables=payload.deliverables,
        creator_overrides=payload.creator_overrides,
        selected_creator_ids=payload.selected_creator_ids,
    )
    db.add(job)
    for selection_index, creator_id in enumerate(payload.selected_creator_ids):
        db.add(
            OutreachPitch(
                outreach_job_id=outreach_job_id,
                creator_id=creator_id,
                selection_index=selection_index,
                status="PENDING",
                available_channels=available_channels(leads_by_id[creator_id]),
            )
        )
    await db.commit()

    if payload.auto_start:
        try:
            await inngest_client.send(
                inngest.Event(
                    name="outreach/run",
                    data={
                        "outreach_job_id": job.outreach_job_id,
                        "campaign_id": job.campaign_id,
                        "user_id": user.user_id,
                        "run_id": job.run_id,
                        "thread_id": job.thread_id,
                    },
                )
            )
        except Exception as exc:
            job.status = "FAILED"
            job.error_message = "Unable to enqueue outreach workflow"
            await db.commit()
            raise HTTPException(503, "Unable to enqueue outreach workflow") from exc

    return _job_response(job)


@router.get("/campaigns/{campaign_id}/jobs", response_model=list[OutreachJobResponse])
async def list_outreach_jobs(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OutreachJob)
        .where(OutreachJob.campaign_id == campaign_id, OutreachJob.user_id == user.user_id)
        .order_by(OutreachJob.created_at.desc())
    )
    return [_job_response(job) for job in result.scalars().all()]


@router.get("/campaigns/{campaign_id}/latest-job", response_model=OutreachJobDetailResponse)
async def get_latest_outreach_job(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OutreachJob)
        .options(selectinload(OutreachJob.pitches))
        .where(OutreachJob.campaign_id == campaign_id, OutreachJob.user_id == user.user_id)
        .order_by(OutreachJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "No outreach jobs found for this campaign")
    return _build_job_detail_response(job)


def _build_job_detail_response(job: OutreachJob) -> OutreachJobDetailResponse:
    return OutreachJobDetailResponse(
        **_job_response(job).model_dump(),
        selected_creator_ids=job.selected_creator_ids or [],
        collaboration_type=job.collaboration_type,
        deliverables=job.deliverables or [],
        creator_overrides=job.creator_overrides or {},
        pitches=[
            {
                "pitch_id": pitch.pitch_id,
                "creator_id": pitch.creator_id,
                "status": pitch.status,
                "available_channels": pitch.available_channels or [],
                "pitch_bundle": pitch.pitch_bundle,
                "validation_errors": pitch.validation_errors or [],
                "repair_count": pitch.repair_count or 0,
            }
            for pitch in sorted(job.pitches, key=lambda item: item.selection_index)
        ],
        pitch_pack=job.pitch_pack,
        generation_stats=job.generation_stats,
        error_message=job.error_message,
    )


@router.get("/jobs/{outreach_job_id}", response_model=OutreachJobDetailResponse)
async def get_outreach_job(
    outreach_job_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OutreachJob)
        .options(selectinload(OutreachJob.pitches))
        .where(OutreachJob.outreach_job_id == outreach_job_id, OutreachJob.user_id == user.user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Outreach job not found")
    return _build_job_detail_response(job)


@router.post("/jobs/{outreach_job_id}/start", response_model=OutreachJobResponse)
async def start_outreach_job(
    outreach_job_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OutreachJob).where(OutreachJob.outreach_job_id == outreach_job_id, OutreachJob.user_id == user.user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Outreach job not found")
    if job.status == "PENDING":
        return _job_response(job)
    if job.status == "COMPLETED":
        raise HTTPException(409, "Outreach job has already completed")

    new_run_id = str(uuid.uuid4())
    job.run_id = new_run_id
    job.status = "PENDING"
    job.error_message = None
    await db.commit()
    try:
        await inngest_client.send(
            inngest.Event(
                name="outreach/run",
                data={
                    "outreach_job_id": job.outreach_job_id,
                    "campaign_id": job.campaign_id,
                    "user_id": user.user_id,
                    "run_id": new_run_id,
                    "thread_id": job.thread_id,
                },
            )
        )
    except Exception as exc:
        job.status = "FAILED"
        job.error_message = "Unable to enqueue outreach workflow"
        await db.commit()
        raise HTTPException(503, "Unable to enqueue outreach workflow") from exc
    return _job_response(job)