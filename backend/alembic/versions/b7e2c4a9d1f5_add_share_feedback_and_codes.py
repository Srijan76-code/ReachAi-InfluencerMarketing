"""add share feedback, sessions and email codes

Revision ID: b7e2c4a9d1f5
Revises: a1d4f7c2e9b3
Create Date: 2026-11-05 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e2c4a9d1f5"
down_revision: Union[str, Sequence[str], None] = "a1d4f7c2e9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reviewer feedback on shared creators, and email codes that unlock contact details."""
    op.add_column("share_links", sa.Column("code_hash", sa.String(), nullable=True))
    op.add_column("share_links", sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("share_links", sa.Column("code_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("share_links", sa.Column("code_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("share_links", sa.Column("codes_window_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("share_links", sa.Column("codes_window_count", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "share_sessions",
        sa.Column("session_hash", sa.String(), nullable=False),
        sa.Column("link_id", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["link_id"], ["share_links.link_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_hash"),
    )
    op.create_index(op.f("ix_share_sessions_link_id"), "share_sessions", ["link_id"], unique=False)
    op.create_table(
        "share_feedback",
        sa.Column("feedback_id", sa.String(), nullable=False),
        sa.Column("link_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.campaign_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["link_id"], ["share_links.link_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feedback_id"),
        sa.UniqueConstraint("link_id", "creator_id", name="uq_share_feedback_link_creator"),
    )
    op.create_index(op.f("ix_share_feedback_campaign_id"), "share_feedback", ["campaign_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_share_feedback_campaign_id"), table_name="share_feedback")
    op.drop_table("share_feedback")
    op.drop_index(op.f("ix_share_sessions_link_id"), table_name="share_sessions")
    op.drop_table("share_sessions")
    for col in ("codes_window_count", "codes_window_start", "code_sent_at", "code_attempts", "code_expires_at", "code_hash"):
        op.drop_column("share_links", col)
