"""Read-only share links for a campaign's shortlist (roadmap F1.18).

One row per link: a personal link (one person, by email) or an "anyone with the link" link.
Viewers see the shortlist; reviewers can also approve or reject each creator. Contact details are never
shown through a link (decided Nov 4); prices only when the owner turns them on for that link.

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
    role = Column(String, nullable=False, default="viewer")  # viewer | reviewer (personal links only)
    show_prices = Column(Boolean, nullable=False, default=False)
    creator_ids = Column(JSONB, nullable=True)  # lead ids shared; None = the whole shortlist

    expires_at = Column(DateTime(timezone=True), nullable=True)  # anyone links: 30 days; person links: until removed
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    view_count = Column(Integer, nullable=False, default=0)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)
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


class ShareEvent(Base):
    """The sharing activity log: a link was opened (at most once per OPEN_EVENT_GAP_MINUTES per link) or a
    reviewer gave feedback. Feeds the owner's Activity feed."""

    __tablename__ = "share_events"

    event_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    link_id = Column(String, ForeignKey("share_links.link_id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)  # opened | feedback
    creator_id = Column(String, nullable=True)  # feedback: which creator
    verdict = Column(String, nullable=True)  # feedback: yes | no | None
    comment = Column(Text, nullable=True)  # feedback: the comment at that moment
    created_at = Column(DateTime(timezone=True), server_default=func.now())
