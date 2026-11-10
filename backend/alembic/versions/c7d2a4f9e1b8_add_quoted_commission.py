"""add the commission a creator asked for

Revision ID: c7d2a4f9e1b8
Revises: b5c1e8f3a9d4
Create Date: 2026-11-05 06:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d2a4f9e1b8"
down_revision: Union[str, Sequence[str], None] = "b5c1e8f3a9d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("creator_deals", sa.Column("quoted_commission_pct", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("creator_deals", "quoted_commission_pct")
