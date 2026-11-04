"""drop share-link contact sharing and email codes

Revision ID: c4f8e1a2b6d9
Revises: b7e2c4a9d1f5
Create Date: 2026-11-05 12:00:00

Decided Nov 4: contact details are never shared through links, so the email-code step and its
storage go (no data lost: the feature was never switched on).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f8e1a2b6d9"
down_revision: Union[str, Sequence[str], None] = "b7e2c4a9d1f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CODE_COLUMNS = ("code_hash", "code_expires_at", "code_attempts", "code_sent_at", "codes_window_start", "codes_window_count")


def upgrade() -> None:
    op.drop_index(op.f("ix_share_sessions_link_id"), table_name="share_sessions")
    op.drop_table("share_sessions")
    for col in CODE_COLUMNS:
        op.drop_column("share_links", col)
    op.drop_column("share_links", "show_contacts")


def downgrade() -> None:
    op.add_column("share_links", sa.Column("show_contacts", sa.Boolean(), server_default=sa.false(), nullable=False))
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
