"""add creator database (creators, persons, snapshots, judgments, links, embeddings)

Revision ID: d7a2e5c9b1f3
Revises: c3f1a9d4e2b0
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models.creator import Vector

revision: str = "d7a2e5c9b1f3"
down_revision: Union[str, Sequence[str], None] = "c3f1a9d4e2b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768  # keep in sync with app.creators.constants.EMBEDDING_DIM


def _json():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "creator_persons",
        sa.Column("person_id", sa.String(), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("primary_contact", _json(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )

    op.create_table(
        "creators",
        sa.Column("creator_id", sa.String(), primary_key=True),
        sa.Column("person_id", sa.String(), sa.ForeignKey("creator_persons.person_id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("platform_id", sa.String(), nullable=False),
        sa.Column("handle", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("tier", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("niche", sa.String(), nullable=True),
        sa.Column("contacts", _json(), nullable=True),
        sa.Column("cross_links", _json(), nullable=True),
        sa.Column("external_links", _json(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("latest_metrics", _json(), nullable=True),
        sa.Column("latest_engagement_rate", sa.Float(), nullable=True),
        sa.Column("latest_median_views", sa.Float(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("platform", "platform_id", name="uq_creators_platform_account"),
    )
    op.create_index("ix_creators_person_id", "creators", ["person_id"])
    op.create_index("ix_creators_data_expires_at", "creators", ["data_expires_at"])
    op.create_index("ix_creators_platform_tier", "creators", ["platform", "tier"])

    op.create_table(
        "creator_snapshots",
        sa.Column("snapshot_id", sa.String(), primary_key=True),
        sa.Column("creator_id", sa.String(), sa.ForeignKey("creators.creator_id", ondelete="CASCADE"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("recent_posts", _json(), nullable=True),
        sa.Column("metrics", _json(), nullable=True),
    )
    op.create_index("ix_creator_snapshots_creator_time", "creator_snapshots", ["creator_id", "captured_at"])

    op.create_table(
        "creator_judgments",
        sa.Column("judgment_id", sa.String(), primary_key=True),
        sa.Column("creator_id", sa.String(), sa.ForeignKey("creators.creator_id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("brief_hash", sa.String(), nullable=False),
        sa.Column("questions_version", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("answers", _json(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("creator_id", "content_hash", "brief_hash", "questions_version", name="uq_creator_judgment_key"),
    )
    op.create_index("ix_creator_judgments_creator_id", "creator_judgments", ["creator_id"])
    op.create_index("ix_creator_judgments_campaign_id", "creator_judgments", ["campaign_id"])

    op.create_table(
        "person_links",
        sa.Column("creator_id", sa.String(), sa.ForeignKey("creators.creator_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("person_id", sa.String(), sa.ForeignKey("creator_persons.person_id", ondelete="CASCADE"), nullable=False),
        sa.Column("link_source", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_person_links_person_id", "person_links", ["person_id"])

    op.create_table(
        "creator_embeddings",
        sa.Column("creator_id", sa.String(), sa.ForeignKey("creators.creator_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("text_hash", sa.String(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    # Approximate nearest-neighbour index for cosine distance (HNSW, pgvector >= 0.5).
    op.execute(
        "CREATE INDEX ix_creator_embeddings_hnsw ON creator_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_creator_embeddings_hnsw")
    op.drop_table("creator_embeddings")
    op.drop_index("ix_person_links_person_id", table_name="person_links")
    op.drop_table("person_links")
    op.drop_index("ix_creator_judgments_campaign_id", table_name="creator_judgments")
    op.drop_index("ix_creator_judgments_creator_id", table_name="creator_judgments")
    op.drop_table("creator_judgments")
    op.drop_index("ix_creator_snapshots_creator_time", table_name="creator_snapshots")
    op.drop_table("creator_snapshots")
    op.drop_index("ix_creators_platform_tier", table_name="creators")
    op.drop_index("ix_creators_data_expires_at", table_name="creators")
    op.drop_index("ix_creators_person_id", table_name="creators")
    op.drop_table("creators")
    op.drop_table("creator_persons")
    # The vector extension is left installed: other databases objects may use it.
