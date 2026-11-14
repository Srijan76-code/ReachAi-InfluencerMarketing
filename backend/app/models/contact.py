"""Who has been contacted, and who must never be (spec §7.1 steps 7–8, roadmap F6.1)."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class ContactHistory(Base):
    """One row per founder and address: when they first wrote to that person, and how it last went. Used to
    warn before contacting someone the same founder already contacted recently (another campaign)."""

    __tablename__ = "contact_history"
    __table_args__ = (UniqueConstraint("user_id", "address_hash", name="uq_contact_history_user_address"),)

    contact_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    address_hash = Column(String, nullable=False)  # sha256 of the lowercased email or handle
    channel = Column(String, nullable=False, default="email")
    campaign_id = Column(String, nullable=True)  # the latest campaign that contacted them
    first_contacted_at = Column(DateTime(timezone=True), server_default=func.now())
    last_contacted_at = Column(DateTime(timezone=True), server_default=func.now())
    last_outcome = Column(String, nullable=True)  # sent | replied | agreed | declined | bounced | opted_out


class Suppression(Base):
    """Addresses nobody using ReachAI may email again: the person opted out, the address bounced, or they
    complained. Checked before every send, across all users. Only a hash is stored."""

    __tablename__ = "suppression_list"
    address_hash = Column(String, primary_key=True)
    reason = Column(String, nullable=False)  # opt_out | bounce | complaint
    created_at = Column(DateTime(timezone=True), server_default=func.now())
