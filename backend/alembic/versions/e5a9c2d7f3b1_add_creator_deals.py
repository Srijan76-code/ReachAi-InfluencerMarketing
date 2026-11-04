"""add creator deals and deal events

Revision ID: e5a9c2d7f3b1
Revises: c4f8e1a2b6d9
Create Date: 2026-11-05 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5a9c2d7f3b1"
down_revision: Union[str, Sequence[str], None] = "c4f8e1a2b6d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deals (spec §8.1): the creators a founder works with, from first contact to paid, and their timeline."""
    op.create_table(
        "creator_deals",
        sa.Column("deal_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("creator_name", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("position", sa.Float(), nullable=False),
        sa.Column("deliverable", sa.String(), nullable=False),
        sa.Column("post_by", sa.Date(), nullable=True),
        sa.Column("deal_type", sa.String(), nullable=False),
        sa.Column("commission_pct", sa.Float(), nullable=True),
        sa.Column("usage_rights", sa.String(), nullable=False),
        sa.Column("exclusivity_days", sa.Integer(), nullable=False),
        sa.Column("disclosure", sa.Boolean(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("quoted_rate", sa.Float(), nullable=True),
        sa.Column("agreed_rate", sa.Float(), nullable=True),
        sa.Column("fair_low", sa.Float(), nullable=True),
        sa.Column("fair_high", sa.Float(), nullable=True),
        sa.Column("typical_views", sa.Float(), nullable=True),
        sa.Column("post_url", sa.String(), nullable=True),
        sa.Column("live_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_amount", sa.Float(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_ref", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.campaign_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("deal_id"),
        sa.UniqueConstraint("campaign_id", "creator_id", name="uq_creator_deals_campaign_creator"),
    )
    op.create_index(op.f("ix_creator_deals_campaign_id"), "creator_deals", ["campaign_id"], unique=False)
    op.create_table(
        "deal_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("deal_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["creator_deals.deal_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_deal_events_deal_id"), "deal_events", ["deal_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_deal_events_deal_id"), table_name="deal_events")
    op.drop_table("deal_events")
    op.drop_index(op.f("ix_creator_deals_campaign_id"), table_name="creator_deals")
    op.drop_table("creator_deals")
