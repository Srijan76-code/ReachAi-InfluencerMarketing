"""Add the contact ledger and the suppression list (F6.1)

Revision ID: a3c5e7f9b1d2
Revises: 205140d6a74e
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3c5e7f9b1d2"
down_revision: Union[str, None] = "205140d6a74e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_history",
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("address_hash", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=True),
        sa.Column("first_contacted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("last_outcome", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("contact_id"),
        sa.UniqueConstraint("user_id", "address_hash", name="uq_contact_history_user_address"),
    )
    op.create_index(op.f("ix_contact_history_user_id"), "contact_history", ["user_id"], unique=False)
    op.create_table(
        "suppression_list",
        sa.Column("address_hash", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("address_hash"),
    )


def downgrade() -> None:
    op.drop_table("suppression_list")
    op.drop_index(op.f("ix_contact_history_user_id"), table_name="contact_history")
    op.drop_table("contact_history")
