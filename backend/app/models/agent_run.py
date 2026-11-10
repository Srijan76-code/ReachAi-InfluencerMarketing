import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.sql import func

from app.db.base import Base


class AgentRun(Base):
    """One creator search started by an agent over MCP. Counted per user per day to cap spend (spec §15.5)."""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_user_created", "user_id", "created_at"),)

    agent_run_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
