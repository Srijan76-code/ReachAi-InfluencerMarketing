import uuid
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clerk_id = Column(String, unique=True, nullable=False)

    credits = Column(Integer, default=10)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete")