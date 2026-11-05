"""several posts per deal, tracking links and clicks, and the channel per deal

Revision ID: f4b2c8d1e6a9
Revises: e3f9a7c2b5d8
Create Date: 2026-11-05 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4b2c8d1e6a9"
down_revision: Union[str, Sequence[str], None] = "e3f9a7c2b5d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("creator_deals", sa.Column("channel", sa.String(), nullable=True))
    op.add_column("creator_deals", sa.Column("tracking_code", sa.String(), nullable=True))
    op.add_column("creator_deals", sa.Column("pay_when", sa.String(), nullable=True))
    op.create_table(
        "deal_posts",
        sa.Column("post_id", sa.String(), primary_key=True),
        sa.Column("deal_id", sa.String(), sa.ForeignKey("creator_deals.deal_id", ondelete="CASCADE"), nullable=False),
        sa.Column("deliverable", sa.String(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("post_url", sa.String(), nullable=True),
        sa.Column("live_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_deal_posts_deal_id", "deal_posts", ["deal_id"])
    op.create_table(
        "tracking_links",
        sa.Column("slug", sa.String(), primary_key=True),
        sa.Column("deal_id", sa.String(), sa.ForeignKey("creator_deals.deal_id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.campaign_id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_url", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tracking_links_deal_id", "tracking_links", ["deal_id"])
    op.create_index("ix_tracking_links_campaign_id", "tracking_links", ["campaign_id"])
    op.create_table(
        "link_clicks",
        sa.Column("click_id", sa.String(), primary_key=True),
        sa.Column("slug", sa.String(), sa.ForeignKey("tracking_links.slug", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_link_clicks_slug", "link_clicks", ["slug"])
    op.create_index("ix_link_clicks_created_at", "link_clicks", ["created_at"])


def downgrade() -> None:
    op.drop_table("link_clicks")
    op.drop_table("tracking_links")
    op.drop_table("deal_posts")
    for c in ("pay_when", "tracking_code", "channel"):
        op.drop_column("creator_deals", c)
