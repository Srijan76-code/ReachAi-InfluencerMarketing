import uuid

from sqlalchemy import JSON, Column, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class CostEvent(Base):
    """One row per paid external call (LLM, Jev, data providers). See spec §5.2."""

    __tablename__ = "cost_events"

    event_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    run_id = Column(String, nullable=True, index=True)

    provider = Column(String, nullable=False, index=True)  # e.g. "groq", "google", "typesafe", "apify"
    sku = Column(String, nullable=False)  # model or product name
    route = Column(String, nullable=True)  # LLM route or caller name
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    units = Column(Integer, nullable=True)  # non-token units (results, profiles, quota)
    usd = Column(Numeric(12, 6), nullable=True)  # null when the price is unknown
    meta = Column(JSONType, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
