"""add run_strategy and run_candidates

Revision ID: e4b8c1d6a2f9
Revises: d7a2e5c9b1f3
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4b8c1d6a2f9"
down_revision: Union[str, Sequence[str], None] = "d7a2e5c9b1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "run_strategy",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), nullable=True),
        sa.Column("brief_hash", sa.String(), nullable=True),
        sa.Column("strategy", _json(), nullable=False),
        sa.Column("platforms", _json(), nullable=True),
        sa.Column("warnings", _json(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_run_strategy_campaign_id", "run_strategy", ["campaign_id"])
    op.create_index("ix_run_strategy_brief_hash", "run_strategy", ["brief_hash"])

    op.create_table(
        "run_candidates",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("creator_id", sa.String(), primary_key=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("found_via", sa.String(), nullable=True),
        sa.Column("mode", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("metrics", _json(), nullable=True),
        sa.Column("fit", sa.Float(), nullable=True),
        sa.Column("health", sa.Float(), nullable=True),
        sa.Column("risk", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("deal_status", sa.String(), nullable=True),
        sa.Column("flags", _json(), nullable=True),
        sa.Column("drop_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_run_candidates_run_score", "run_candidates", ["run_id", "final_score"])


def downgrade() -> None:
    op.drop_index("ix_run_candidates_run_score", table_name="run_candidates")
    op.drop_table("run_candidates")
    op.drop_index("ix_run_strategy_brief_hash", table_name="run_strategy")
    op.drop_index("ix_run_strategy_campaign_id", table_name="run_strategy")
    op.drop_table("run_strategy")
