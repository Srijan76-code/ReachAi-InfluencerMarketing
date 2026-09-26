"""add durable workflow identity and status

Revision ID: 7a1d9c2e4f10
Revises: ce92f6ffce37
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7a1d9c2e4f10"
down_revision: Union[str, Sequence[str], None] = "ce92f6ffce37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("run_id", sa.String(), nullable=True))
    op.add_column("campaigns", sa.Column("thread_id", sa.String(), nullable=True))
    op.add_column(
        "campaigns",
        sa.Column(
            "workflow_status",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index("ix_campaigns_run_id", "campaigns", ["run_id"], unique=True)
    op.create_index("ix_campaigns_thread_id", "campaigns", ["thread_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_campaigns_thread_id", table_name="campaigns")
    op.drop_index("ix_campaigns_run_id", table_name="campaigns")
    op.drop_column("campaigns", "workflow_status")
    op.drop_column("campaigns", "thread_id")
    op.drop_column("campaigns", "run_id")
