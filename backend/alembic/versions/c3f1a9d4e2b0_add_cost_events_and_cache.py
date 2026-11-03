"""add cost_events and cache_entries

Revision ID: c3f1a9d4e2b0
Revises: b84e6d7f2c11
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3f1a9d4e2b0"
down_revision: Union[str, Sequence[str], None] = "b84e6d7f2c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cost_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("campaign_id", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("route", sa.String(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("units", sa.Integer(), nullable=True),
        sa.Column("usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    for column in ("user_id", "campaign_id", "run_id", "provider", "created_at"):
        op.create_index(f"ix_cost_events_{column}", "cost_events", [column])

    op.create_table(
        "cache_entries",
        sa.Column("namespace", sa.String(), primary_key=True),
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_cache_entries_expires_at", "cache_entries", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_cache_entries_expires_at", table_name="cache_entries")
    op.drop_table("cache_entries")
    for column in ("user_id", "campaign_id", "run_id", "provider", "created_at"):
        op.drop_index(f"ix_cost_events_{column}", table_name="cost_events")
    op.drop_table("cost_events")
