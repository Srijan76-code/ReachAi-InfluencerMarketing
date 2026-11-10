"""Per-run records for the discovery graph (spec §4.14): the strategy, and every creator a run
looked at, how far it got and why it was dropped. Used for live results, status and debugging."""

from sqlalchemy import JSON, Column, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class RunStrategy(Base):
    __tablename__ = "run_strategy"

    run_id = Column(String, primary_key=True)
    campaign_id = Column(String, nullable=True, index=True)
    brief_hash = Column(String, nullable=True, index=True)  # reuse the strategy for an identical brief
    strategy = Column(JSONType, nullable=False)
    platforms = Column(JSONType, nullable=True)  # {platform: {selected, weight, note, mode}}
    warnings = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RunCandidate(Base):
    __tablename__ = "run_candidates"
    __table_args__ = (Index("ix_run_candidates_run_score", "run_id", "final_score"),)

    run_id = Column(String, primary_key=True)
    creator_id = Column(String, primary_key=True)
    platform = Column(String, nullable=False)
    found_via = Column(String, nullable=True)  # search, trend_search, video_search, creator_db, ...
    mode = Column(String, nullable=True)  # full | probe | expand
    stage = Column(String, nullable=False)  # fetched, filtered_out, measured, judged, scored, shortlisted
    metrics = Column(JSONType, nullable=True)
    fit = Column(Float, nullable=True)
    health = Column(Float, nullable=True)
    risk = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    deal_status = Column(String, nullable=True)
    flags = Column(JSONType, nullable=True)
    drop_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
