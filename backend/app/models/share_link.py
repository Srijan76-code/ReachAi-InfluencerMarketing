"""Read-only share links for a campaign's shortlist (roadmap F1.18).

One row per link: a personal link (one person, by email) or an "anyone with the link" link.
Every link is view-only. Contact details are never shown through a link until email codes exist
(PR 4b); prices only when the owner turns them on for that link.

The token is stored as-is (not hashed) so the owner can copy a link again at any time, like Drive.
Hashing would only protect against someone who can read this database, and they can already read
the campaign's leads directly, so it would add nothing.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
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
