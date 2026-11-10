import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ApiKey(Base):
    """A personal API key for agents that cannot do OAuth. Only the SHA-256 hash is stored."""

    __tablename__ = "api_keys"

    key_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String, nullable=False)
    prefix = Column(String, nullable=False)  # first characters, so the user can recognise a key
    key_hash = Column(String, nullable=False, unique=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
