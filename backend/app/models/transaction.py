import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class TransactionType(enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"))

    amount = Column(Integer, nullable=False)

    type = Column(Enum(TransactionType), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")