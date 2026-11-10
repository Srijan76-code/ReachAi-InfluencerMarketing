"""add indexes for campaign list and saved leads

Revision ID: 8e6c2e1ac3e7
Revises: e4b8c1d6a2f9
Create Date: 2026-11-04 07:25:50.353171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e6c2e1ac3e7'
down_revision: Union[str, Sequence[str], None] = 'e4b8c1d6a2f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Campaign list (user_id + newest first) and saved leads by campaign were full table scans.
    Also aligns the outreach_pitches index name with the model (roadmap K7)."""
    op.create_index('ix_campaigns_user_created', 'campaigns', ['user_id', 'created_at'], unique=False)
    op.drop_index(op.f('ix_outreach_pitches_job_id'), table_name='outreach_pitches')
    op.create_index(op.f('ix_outreach_pitches_outreach_job_id'), 'outreach_pitches', ['outreach_job_id'], unique=False)
    op.create_index(op.f('ix_saved_leads_campaign_id'), 'saved_leads', ['campaign_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_leads_campaign_id'), table_name='saved_leads')
    op.drop_index(op.f('ix_outreach_pitches_outreach_job_id'), table_name='outreach_pitches')
    op.create_index(op.f('ix_outreach_pitches_job_id'), 'outreach_pitches', ['outreach_job_id'], unique=False)
    op.drop_index('ix_campaigns_user_created', table_name='campaigns')
