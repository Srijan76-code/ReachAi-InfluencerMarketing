"""Credits ledger, reservations and each user's plan (spec §5.3)."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base


class CreditEntry(Base):
    """One change to a user's credits. A balance is always the sum of entries, never a stored number."""

    __tablename__ = "credit_ledger"
    __table_args__ = (
        # The same grant, expiry, reservation or release can never be written twice.
        UniqueConstraint("user_id", "reason", "ref_type", "ref_id", "bucket", name="uq_credit_ledger_ref"),
        Index("ix_credit_ledger_user_created", "user_id", "created_at"),
    )

    entry_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    delta = Column(Integer, nullable=False)
    bucket = Column(String, nullable=False)  # monthly | rollover | bonus | pack
    # grant_plan | grant_welcome | grant_pack | grant_referral | rollover | expire | reserve | release | refund | adjust
    reason = Column(String, nullable=False)
    ref_type = Column(String, nullable=True)  # period | reservation | welcome | admin
    ref_id = Column(String, nullable=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CreditReservation(Base):
    """Credits held for one search while it runs. Committed when it finishes, released if it fails."""

    __tablename__ = "credit_reservations"
    __table_args__ = (
        Index("ix_credit_reservations_user_created", "user_id", "created_at"),
        Index("ix_credit_reservations_status_expires", "status", "expires_at"),
    )

    reservation_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.campaign_id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String, nullable=False, unique=True)
    amount = Column(Integer, nullable=False)
    buckets = Column(JSONB, nullable=False, default=dict)  # {"monthly": 1, ...}: where the credits came from
    platforms = Column(JSONB, nullable=False, default=list)
    status = Column(String, nullable=False, default="held")  # held | committed | released | refunded
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    settled_at = Column(DateTime(timezone=True), nullable=True)


class Subscription(Base):
    """A user's plan and current credit period. Every user has one (Free until they pay)."""

    __tablename__ = "subscriptions"

    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    plan = Column(String, nullable=False, default="free")  # free | solo | pro
    interval = Column(String, nullable=False, default="month")  # month | year
    status = Column(String, nullable=False, default="active")  # active | past_due | cancelled
    provider = Column(String, nullable=True)  # dodo (later)
    provider_subscription_id = Column(String, nullable=True, unique=True)
    provider_customer_id = Column(String, nullable=True, index=True)
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Payment(Base):
    """A payment reported by the payment provider (subscription charge or credit pack)."""

    __tablename__ = "payments"

    payment_id = Column(String, primary_key=True)  # the provider's id, e.g. pay_...
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False, default="dodo")
    kind = Column(String, nullable=False)  # subscription | pack
    item = Column(String, nullable=True)  # solo_monthly | pack_10 | ...
    amount_minor = Column(Integer, nullable=True)
    currency = Column(String, nullable=True)
    status = Column(String, nullable=False)  # succeeded | refunded
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BillingEvent(Base):
    """Webhook deliveries already handled, by the provider's webhook id (they can arrive more than once)."""

    __tablename__ = "billing_events"

    event_id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    user_id = Column(String, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
