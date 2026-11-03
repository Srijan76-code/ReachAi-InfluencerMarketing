from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class CacheEntry(Base):
    """Shared read-through cache (spec §4.14). Namespaces: "search", "llm", ..."""

    __tablename__ = "cache_entries"

    namespace = Column(String, primary_key=True)
    key = Column(String, primary_key=True)  # sha256 of the key parts
    value = Column(JSONType, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
