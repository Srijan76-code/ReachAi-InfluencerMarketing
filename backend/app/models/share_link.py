"""Read-only share links for a campaign's shortlist (roadmap F1.18).

One row per link: a personal link (one person, by email) or an "anyone with the link" link.
Every link is view-only. Contact details are never shown through a link until email codes exist
(PR 4b); prices only when the owner turns them on for that link.

The token is stored as-is (not hashed) so the owner can copy a link again at any time, like Drive.
Hashing would only protect against someone who can read this database, and they can already read
the campaign's leads directly, so it would add nothing.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base


class ShareLink(Base):
    __tablename__ = "share_links"

    link_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    token = Column(String, nullable=False, unique=True, index=True)

    kind = Column(String, nullable=False)  # person | anyone
    email = Column(String, nullable=True)  # person links: who it's for (shown to the owner, never to viewers)
    role = Column(String, nullable=False, default="viewer")  # viewer (reviewer comes with feedback, PR 4b)
    show_prices = Column(Boolean, nullable=False, default=False)
    show_contacts = Column(Boolean, nullable=False, default=False)  # needs email codes (PR 4b); always false for now
    creator_ids = Column(JSONB, nullable=True)  # lead ids shared; None = the whole shortlist

    expires_at = Column(DateTime(timezone=True), nullable=True)  # anyone links: 30 days; person links: until removed
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    view_count = Column(Integer, nullable=False, default=0)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # one-time email code that unlocks contact details on a personal link (only one active code at a time)
    code_hash = Column(String, nullable=True)
    code_expires_at = Column(DateTime(timezone=True), nullable=True)
    code_attempts = Column(Integer, nullable=False, default=0)
    code_sent_at = Column(DateTime(timezone=True), nullable=True)
    codes_window_start = Column(DateTime(timezone=True), nullable=True)  # for "at most N codes an hour"
    codes_window_count = Column(Integer, nullable=False, default=0)


class ShareSession(Base):
    """A browser that proved it can read the invited inbox: sees contact details until it expires.
    Only a hash of the session token is stored."""

    __tablename__ = "share_sessions"

    session_hash = Column(String, primary_key=True)
    link_id = Column(String, ForeignKey("share_links.link_id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ShareFeedback(Base):
    """A reviewer's verdict and comment on one creator, given through their share link."""

    __tablename__ = "share_feedback"
    __table_args__ = (UniqueConstraint("link_id", "creator_id", name="uq_share_feedback_link_creator"),)

    feedback_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    link_id = Column(String, ForeignKey("share_links.link_id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(String, nullable=False)  # the lead's id
    verdict = Column(String, nullable=True)  # yes | no | None (comment only)
    comment = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
