"""What the reply agent has learned (spec §8.6c): facts the founder told it, rules about the founder's style, and
lessons from Jev's checks. Founder-scoped, visible and deletable. Plus the questions it asked the founder."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base


class AgentMemory(Base):
    __tablename__ = "agent_memory"
    __table_args__ = (Index("ix_agent_memory_user_kind", "user_id", "kind"),)

    memory_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(String, nullable=True)  # None: applies to every campaign of this founder
    kind = Column(String, nullable=False)  # fact | style | lesson
    key = Column(String, nullable=True)  # lessons: the rubric check; facts: the question it answers
    text = Column(Text, nullable=False)
    source = Column(String, nullable=True)  # founder_answer | founder_edit | jev
    count = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FounderQuestion(Base):
    """Something a creator asked that ReachAI doesn't know: asked to the founder by email and in the chat."""

    __tablename__ = "founder_questions"

    question_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(String, ForeignKey("creator_deals.deal_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    reply_event_id = Column(String, nullable=True)  # the creator message that raised it
    questions = Column(JSONB, nullable=False)  # ["What are your contract terms?"]
    creator_text = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="open")  # open | answered | dropped
    answer = Column(Text, nullable=True)
    gmail_thread_id = Column(String, nullable=True)  # the email to the founder: their reply in it is the answer
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    answered_at = Column(DateTime(timezone=True), nullable=True)
