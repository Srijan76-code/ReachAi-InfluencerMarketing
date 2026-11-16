import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class AgentGrant(Base):
    """What the founder let their agent do (F9.8, 8b). The agent asks (`request_permission`), the founder reads it in
    plain words on the website and approves once, with limits and an end date; they can remove it any time. An agent can't
    approve its own request: approving needs the website sign-in."""

    __tablename__ = "agent_grants"

    grant_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=True, index=True)
    ability = Column(String, nullable=False)  # app/agent/grants.py ABILITIES
    mode = Column(String, nullable=False, default="ask")  # ask: the founder says yes in chat each time | unattended: pre-approved within the limits
    per_day = Column(Integer, nullable=True)  # sends a day, for abilities that send
    client_name = Column(String, nullable=False)  # what the agent calls itself: shown, never trusted
    user_code = Column(String, nullable=False, unique=True, index=True)  # "BCDF-GHJK", for the approval page
    status = Column(String, nullable=False, default="pending")  # pending | approved | denied | revoked
    requested_days = Column(Integer, nullable=False, default=7)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    request_expires_at = Column(DateTime(timezone=True), nullable=False)  # an unanswered request lapses
    approved_at = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)  # set when approved
    revoked_at = Column(DateTime(timezone=True), nullable=True)
