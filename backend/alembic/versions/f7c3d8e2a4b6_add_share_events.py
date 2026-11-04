"""add share events (sharing activity log)

Revision ID: f7c3d8e2a4b6
Revises: e5a9c2d7f3b1
Create Date: 2026-11-05 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7c3d8e2a4b6"
down_revision: Union[str, Sequence[str], None] = "e5a9c2d7f3b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Who opened a shared shortlist and when, and every reviewer reaction, for the owner's Activity feed."""
    op.create_table(
        "share_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("link_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.campaign_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["link_id"], ["share_links.link_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_share_events_campaign_id"), "share_events", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_share_events_link_id"), "share_events", ["link_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_share_events_link_id"), table_name="share_events")
    op.drop_index(op.f("ix_share_events_campaign_id"), table_name="share_events")
    op.drop_table("share_events")
