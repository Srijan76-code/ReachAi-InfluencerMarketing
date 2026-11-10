"""Track: found posts and their numbers, daily stats, conversions, payment method

Revision ID: a7c3e9f2d4b1
Revises: f4b2c8d1e6a9
Create Date: 2026-11-05 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7c3e9f2d4b1"
down_revision: Union[str, Sequence[str], None] = "f4b2c8d1e6a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POST_COLUMNS = [
    ("video_id", sa.String()), ("title", sa.String()), ("thumbnail_url", sa.String()), ("found_by", sa.String()),
    ("views", sa.Integer()), ("likes", sa.Integer()), ("comments", sa.Integer()),
    ("stats_at", sa.DateTime(timezone=True)), ("comment_summary", postgresql.JSONB(astext_type=sa.Text())),
]


def upgrade() -> None:
    op.add_column("creator_deals", sa.Column("pay_method", sa.String(), nullable=True))
    for name, kind in POST_COLUMNS:
        op.add_column("deal_posts", sa.Column(name, kind, nullable=True))
    op.create_table(
        "post_stats",
        sa.Column("stat_id", sa.String(), primary_key=True),
        sa.Column("post_id", sa.String(), sa.ForeignKey("deal_posts.post_id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.UniqueConstraint("post_id", "day", name="uq_post_stats_post_day"),
    )
    op.create_index("ix_post_stats_post_id", "post_stats", ["post_id"])
    op.create_table(
        "conversions",
        sa.Column("conversion_id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False),
        sa.Column("deal_id", sa.String(), sa.ForeignKey("creator_deals.deal_id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversions_campaign_id", "conversions", ["campaign_id"])
    op.create_index("ix_conversions_deal_id", "conversions", ["deal_id"])


def downgrade() -> None:
    op.drop_table("conversions")
    op.drop_table("post_stats")
    for name, _ in POST_COLUMNS:
        op.drop_column("deal_posts", name)
    op.drop_column("creator_deals", "pay_method")
