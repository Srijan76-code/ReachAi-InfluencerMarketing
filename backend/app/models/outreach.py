import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class OutreachJob(Base):
    __tablename__ = "outreach_jobs"

    outreach_job_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)

    run_id = Column(String, nullable=True, unique=True, index=True)
    thread_id = Column(String, nullable=True, unique=True, index=True)
    status = Column(String, nullable=False, default="CREATED", index=True)

    collaboration_type = Column(String, nullable=True)
    deliverables = Column(JSONB, nullable=True)
    creator_overrides = Column(JSONB, nullable=True)
    selected_creator_ids = Column(JSONB, nullable=True)
    pitch_pack = Column(JSONB, nullable=True)
    generation_stats = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="outreach_jobs")
    pitches = relationship(
        "OutreachPitch",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class OutreachPitch(Base):
    __tablename__ = "outreach_pitches"

    pitch_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    outreach_job_id = Column(
        String,
        ForeignKey("outreach_jobs.outreach_job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creator_id = Column(String, nullable=False, index=True)
    selection_index = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="PENDING", index=True)

    available_channels = Column(JSONB, nullable=True)
    pitch_bundle = Column(JSONB, nullable=True)
    validation_errors = Column(JSONB, nullable=True)
    repair_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job = relationship("OutreachJob", back_populates="pitches")