import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class SavedLead(Base):
    __tablename__ = "saved_leads"

    lead_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"))

    name = Column(String, nullable=True)
    lead_data = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaign = relationship("Campaign", back_populates="saved_leads")