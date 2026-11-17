import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.sql import func

from app.db.base import Base


class DeviceCode(Base):
    """A device login (F9.8): an agent or CLI asks to be connected, the founder approves it once in the browser, and the
    agent receives its own personal API key. The agent keeps the secret `device_code` (only its hash is stored); the
    founder types or opens the short `user_code`."""

    __tablename__ = "device_codes"

    code_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    device_hash = Column(String, nullable=False, unique=True, index=True)  # sha256 of the secret the agent polls with
    user_code = Column(String, nullable=False, unique=True, index=True)  # "BCDF-GHJK", shown to the founder
    client_name = Column(String, nullable=False)  # what the agent calls itself ("Claude Code"): shown, never trusted
    status = Column(String, nullable=False, default="pending")  # pending | approved | denied
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True)  # who approved it
    ip_hash = Column(String, nullable=True, index=True)  # to limit how many codes one address can start

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    last_polled_at = Column(DateTime(timezone=True), nullable=True)
    key_id = Column(String, nullable=True)  # set when the key was handed over (once)
