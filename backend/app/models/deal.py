"""Creator deals (spec §8.1, roadmap F7.1): one row per creator a founder is working with in a campaign,
from first contact to paid, plus a timeline of everything that changed."""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base


class CreatorDeal(Base):
    __tablename__ = "creator_deals"
    __table_args__ = (UniqueConstraint("campaign_id", "creator_id", name="uq_creator_deals_campaign_creator"),)

    deal_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(String, nullable=False)  # the lead's id (platform id)
    platform = Column(String, nullable=False, default="youtube")
    creator_name = Column(String, nullable=True)  # snapshot, in case the lead later disappears

    stage = Column(String, nullable=False, default="contacted")  # see app/deals/constants.py STAGES
    position = Column(Float, nullable=False, default=0)  # order inside a column (drag and drop)

    # what was agreed (the terms that cause disputes when they aren't written down)
    deliverable = Column(String, nullable=False, default="integration")
    post_by = Column(Date, nullable=True)
    deal_type = Column(String, nullable=False, default="flat")
    commission_pct = Column(Float, nullable=True)  # base_plus_commission / affiliate
    usage_rights = Column(String, nullable=False, default="none")
    exclusivity_days = Column(Integer, nullable=False, default=0)
    disclosure = Column(Boolean, nullable=False, default=True)  # #ad / "paid partnership" required
    currency = Column(String, nullable=False, default="USD")
    quoted_rate = Column(Float, nullable=True)  # what the creator asked for
    agreed_rate = Column(Float, nullable=True)

    # our numbers when the deal was added (the panel compares the quote with these)
    fair_low = Column(Float, nullable=True)
    fair_high = Column(Float, nullable=True)
    typical_views = Column(Float, nullable=True)

    post_url = Column(String, nullable=True)  # the live post
    live_at = Column(DateTime(timezone=True), nullable=True)
    paid_amount = Column(Float, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    payment_ref = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DealEvent(Base):
    """The deal's timeline: created, stage changes, price changes, marked paid…"""

    __tablename__ = "deal_events"

    event_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(String, ForeignKey("creator_deals.deal_id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
