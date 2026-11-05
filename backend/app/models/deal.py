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
    quoted_rate = Column(Float, nullable=True)  # what the creator asked for (fee)
    quoted_commission_pct = Column(Float, nullable=True)  # …and the commission they asked for, if any
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

    # email with the creator through the founder's Gmail (F6.5)
    contact_email = Column(String, nullable=True)
    gmail_thread_id = Column(String, nullable=True)
    gmail_subject = Column(String, nullable=True)
    gmail_last_message_id = Column(String, nullable=True)  # the RFC 822 Message-ID our next reply answers
    gmail_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_read_at = Column(DateTime(timezone=True), nullable=True)  # when the founder last opened the chat (unread counts)

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


class AgentProposal(Base):
    """A next step the agent suggests for a deal (spec §7.8, the "Needs you" queue). Nothing happens until the
    founder approves it; numbers in `payload` come from code. `key` stops the same suggestion coming back after
    it was approved or skipped."""

    __tablename__ = "agent_proposals"
    __table_args__ = (UniqueConstraint("deal_id", "key", name="uq_agent_proposals_deal_key"),)

    proposal_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id = Column(String, ForeignKey("creator_deals.deal_id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # see app/agent/constants.py KINDS
    status = Column(String, nullable=False, default="pending")  # pending | approved | skipped | stale
    title = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=True)  # message, amounts, stage…
    result = Column(JSONB, nullable=True)  # what was done: final message, edited or not
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)


class ConnectedAccount(Base):
    """A founder's connected inbox (spec §7.5): Gmail today, Outlook later. The refresh token is encrypted
    (app/gmail/crypto.py) and never leaves the server."""

    __tablename__ = "connected_accounts"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_connected_accounts_user_provider"),)

    account_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False, default="gmail")
    email = Column(String, nullable=False)
    display_name = Column(String, nullable=True)  # the name Gmail shows as the sender ("Srijan Patel")
    refresh_token = Column(Text, nullable=False)  # encrypted
    status = Column(String, nullable=False, default="active")  # active | reconnect
    sent_day = Column(Date, nullable=True)
    sent_today = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
