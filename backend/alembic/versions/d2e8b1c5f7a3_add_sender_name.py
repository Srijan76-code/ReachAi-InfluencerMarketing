"""add the sender name for connected Gmail

Revision ID: d2e8b1c5f7a3
Revises: c7d2a4f9e1b8
Create Date: 2026-11-05 08:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e8b1c5f7a3"
down_revision: Union[str, Sequence[str], None] = "c7d2a4f9e1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("connected_accounts", sa.Column("display_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("connected_accounts", "display_name")
