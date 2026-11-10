"""add agent proposals (the "Needs you" queue)

Revision ID: a3b9d5e1c7f2
Revises: f7c3d8e2a4b6
Create Date: 2026-11-05 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3b9d5e1c7f2"
down_revision: Union[str, Sequence[str], None] = "f7c3d8e2a4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Next steps the agent suggests per deal; each waits for the founder's approval."""
    op.create_table(
        "agent_proposals",
        sa.Column("proposal_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("deal_id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.campaign_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_id"], ["creator_deals.deal_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("proposal_id"),
        sa.UniqueConstraint("deal_id", "key", name="uq_agent_proposals_deal_key"),
    )
    op.create_index(op.f("ix_agent_proposals_campaign_id"), "agent_proposals", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_agent_proposals_deal_id"), "agent_proposals", ["deal_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_proposals_deal_id"), table_name="agent_proposals")
    op.drop_index(op.f("ix_agent_proposals_campaign_id"), table_name="agent_proposals")
    op.drop_table("agent_proposals")
