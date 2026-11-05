"""chat read state, and one row per Gmail message

Revision ID: e3f9a7c2b5d8
Revises: d2e8b1c5f7a3
Create Date: 2026-11-05 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f9a7c2b5d8"
down_revision: Union[str, Sequence[str], None] = "d2e8b1c5f7a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("creator_deals", sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))
    # two syncs at once (page open + cron) could save the same email twice: keep the first copy, and drop the
    # price update recorded with each extra copy (same deal, same moment)
    op.execute("""
        WITH dup AS (
            SELECT event_id, deal_id, created_at FROM (
                SELECT event_id, deal_id, created_at,
                       row_number() OVER (PARTITION BY deal_id, payload->>'gmail_id' ORDER BY created_at, event_id) AS n
                FROM deal_events WHERE payload->>'gmail_id' IS NOT NULL
            ) x WHERE n > 1
        ), gone AS (
            DELETE FROM deal_events e USING dup
            WHERE e.deal_id = dup.deal_id AND e.created_at = dup.created_at
              AND (e.event_id = dup.event_id OR e.type = 'quoted_rate')
            RETURNING e.event_id
        )
        SELECT count(*) FROM gone
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_deal_events_gmail_id ON deal_events (deal_id, (payload->>'gmail_id')) "
               "WHERE payload->>'gmail_id' IS NOT NULL")
    # existing chats count as read, so nobody opens the app to a wall of old "unread" replies
    op.execute("UPDATE creator_deals SET last_read_at = now()")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_deal_events_gmail_id")
    op.drop_column("creator_deals", "last_read_at")
