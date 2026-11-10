"""add share links

Revision ID: a1d4f7c2e9b3
Revises: 57ecb86c788d
Create Date: 2026-11-04 16:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1d4f7c2e9b3"
down_revision: Union[str, Sequence[str], None] = "57ecb86c788d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Read-only share links for a campaign's shortlist (personal or anyone-with-the-link)."""
    op.create_table(
        "share_links",
        sa.Column("link_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("show_prices", sa.Boolean(), nullable=False),
        sa.Column("show_contacts", sa.Boolean(), nullable=False),
        sa.Column("creator_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.campaign_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("link_id"),
    )
    op.create_index(op.f("ix_share_links_campaign_id"), "share_links", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_share_links_token"), "share_links", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_share_links_token"), table_name="share_links")
    op.drop_index(op.f("ix_share_links_campaign_id"), table_name="share_links")
    op.drop_table("share_links")
