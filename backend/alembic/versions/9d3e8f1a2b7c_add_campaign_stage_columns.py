"""add campaign stage columns

Revision ID: 9d3e8f1a2b7c
Revises: 7a1d9c2e4f10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d3e8f1a2b7c"
down_revision: Union[str, Sequence[str], None] = "7a1d9c2e4f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("current_stage", sa.String(), nullable=True))
    op.add_column("campaigns", sa.Column("stage_index", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("campaigns", "stage_index")
    op.drop_column("campaigns", "current_stage")
