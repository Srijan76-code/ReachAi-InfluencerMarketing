import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base
import enum


class CampaignStatus(enum.Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class Campaign(Base):
    __tablename__ = "campaigns"

    campaign_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, nullable=True, unique=True, index=True)
    thread_id = Column(String, nullable=True, unique=True, index=True)

    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"))

    name = Column(String, nullable=True)

    campaign_details = Column(JSONB, nullable=True)
    campaign_leads = Column(JSONB, nullable=True)
    workflow_status = Column(JSONB, nullable=True, default=dict)

    status = Column(Enum(CampaignStatus), default=CampaignStatus.CREATED)
    current_stage = Column(String, nullable=True)
    stage_index = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="campaigns")
    saved_leads = relationship("SavedLead", back_populates="campaign", cascade="all, delete")

