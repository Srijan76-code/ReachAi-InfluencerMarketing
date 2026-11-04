"""add connected inboxes and email threads on deals (Gmail)

Revision ID: b5c1e8f3a9d4
Revises: a3b9d5e1c7f2
Create Date: 2026-11-05 04:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c1e8f3a9d4"
down_revision: Union[str, Sequence[str], None] = "a3b9d5e1c7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """The founder's connected Gmail, and each deal's email thread with the creator."""
    op.create_table(
        "connected_accounts",
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("sent_day", sa.Date(), nullable=True),
        sa.Column("sent_today", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_connected_accounts_user_provider"),
    )
    op.create_index(op.f("ix_connected_accounts_user_id"), "connected_accounts", ["user_id"], unique=False)
    for name, type_ in (("contact_email", sa.String()), ("gmail_thread_id", sa.String()), ("gmail_subject", sa.String()),
                        ("gmail_last_message_id", sa.String()), ("gmail_synced_at", sa.DateTime(timezone=True))):
        op.add_column("creator_deals", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name in ("gmail_synced_at", "gmail_last_message_id", "gmail_subject", "gmail_thread_id", "contact_email"):
        op.drop_column("creator_deals", name)
    op.drop_index(op.f("ix_connected_accounts_user_id"), table_name="connected_accounts")
    op.drop_table("connected_accounts")
