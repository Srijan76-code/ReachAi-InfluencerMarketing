"""add creator avatar url

Revision ID: 57ecb86c788d
Revises: 8e6c2e1ac3e7
Create Date: 2026-11-04 10:24:36.149047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57ecb86c788d'
down_revision: Union[str, Sequence[str], None] = '8e6c2e1ac3e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Profile photo URL from the platform (refreshed or removed with the rest of the creator data)."""
    op.add_column('creators', sa.Column('avatar_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('creators', 'avatar_url')
