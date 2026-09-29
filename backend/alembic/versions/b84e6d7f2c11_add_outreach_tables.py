"""add outreach job and pitch tables

Revision ID: b84e6d7f2c11
Revises: 9d3e8f1a2b7c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b84e6d7f2c11"
down_revision: Union[str, Sequence[str], None] = "9d3e8f1a2b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outreach_jobs",
        sa.Column("outreach_job_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("thread_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("collaboration_type", sa.String(), nullable=True),
        sa.Column("deliverables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("creator_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("selected_creator_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pitch_pack", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generation_stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.campaign_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("outreach_job_id"),
    )
    op.create_index("ix_outreach_jobs_campaign_id", "outreach_jobs", ["campaign_id"])
    op.create_index("ix_outreach_jobs_user_id", "outreach_jobs", ["user_id"])
    op.create_index("ix_outreach_jobs_run_id", "outreach_jobs", ["run_id"], unique=True)
    op.create_index("ix_outreach_jobs_thread_id", "outreach_jobs", ["thread_id"], unique=True)
    op.create_index("ix_outreach_jobs_status", "outreach_jobs", ["status"])

    op.create_table(
        "outreach_pitches",
        sa.Column("pitch_id", sa.String(), nullable=False),
        sa.Column("outreach_job_id", sa.String(), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column("selection_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("available_channels", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pitch_bundle", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("repair_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["outreach_job_id"], ["outreach_jobs.outreach_job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pitch_id"),
    )
    op.create_index("ix_outreach_pitches_job_id", "outreach_pitches", ["outreach_job_id"])
    op.create_index("ix_outreach_pitches_creator_id", "outreach_pitches", ["creator_id"])
    op.create_index("ix_outreach_pitches_status", "outreach_pitches", ["status"])


def downgrade() -> None:
    op.drop_index("ix_outreach_pitches_status", table_name="outreach_pitches")
    op.drop_index("ix_outreach_pitches_creator_id", table_name="outreach_pitches")
    op.drop_index("ix_outreach_pitches_job_id", table_name="outreach_pitches")
    op.drop_table("outreach_pitches")
    op.drop_index("ix_outreach_jobs_status", table_name="outreach_jobs")
    op.drop_index("ix_outreach_jobs_thread_id", table_name="outreach_jobs")
    op.drop_index("ix_outreach_jobs_run_id", table_name="outreach_jobs")
    op.drop_index("ix_outreach_jobs_user_id", table_name="outreach_jobs")
    op.drop_index("ix_outreach_jobs_campaign_id", table_name="outreach_jobs")
    op.drop_table("outreach_jobs")