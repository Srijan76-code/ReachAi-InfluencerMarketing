"""Creator database (spec §4.4, §4.9).

One row per platform account in `creators`; `creator_persons` groups accounts that belong
to the same person. Snapshots keep history (for real growth rates), judgments cache Jev
answers, and embeddings power "similar creator" search.
"""

import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, UserDefinedType

from app.creators.constants import EMBEDDING_DIM
from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> str:
    return str(uuid.uuid4())


class _PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim: int):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"


class Vector(TypeDecorator):
    """pgvector column on Postgres; plain text elsewhere (SQLite tests).
    Reads and writes go through app/creators/repository.py, which handles the casts."""

    impl = Text
    cache_ok = True

    def __init__(self, dim: int = EMBEDDING_DIM):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgVector(self.dim))
        return dialect.type_descriptor(Text())


class CreatorPerson(Base):
    __tablename__ = "creator_persons"

    person_id = Column(String, primary_key=True, default=_uuid)
    display_name = Column(String, nullable=True)
    primary_contact = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Creator(Base):
    __tablename__ = "creators"
    __table_args__ = (
        UniqueConstraint("platform", "platform_id", name="uq_creators_platform_account"),
        Index("ix_creators_platform_tier", "platform", "tier"),
    )

    creator_id = Column(String, primary_key=True, default=_uuid)
    person_id = Column(String, ForeignKey("creator_persons.person_id", ondelete="SET NULL"), nullable=True, index=True)
    platform = Column(String, nullable=False)
    platform_id = Column(String, nullable=False)
    handle = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    followers = Column(Integer, nullable=True)
    tier = Column(String, nullable=True)
    country = Column(String, nullable=True)
    language = Column(String, nullable=True)
    niche = Column(String, nullable=True)
    contacts = Column(JSONType, nullable=True)
    cross_links = Column(JSONType, nullable=True)
    external_links = Column(JSONType, nullable=True)
    source = Column(String, nullable=True)

    # Latest computed metrics, copied here so peer and training queries stay fast.
    latest_metrics = Column(JSONType, nullable=True)
    latest_engagement_rate = Column(Float, nullable=True)
    latest_median_views = Column(Float, nullable=True)

    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    data_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CreatorSnapshot(Base):
    __tablename__ = "creator_snapshots"
    __table_args__ = (Index("ix_creator_snapshots_creator_time", "creator_id", "captured_at"),)

    snapshot_id = Column(String, primary_key=True, default=_uuid)
    creator_id = Column(String, ForeignKey("creators.creator_id", ondelete="CASCADE"), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False)
    followers = Column(Integer, nullable=True)
    recent_posts = Column(JSONType, nullable=True)
    metrics = Column(JSONType, nullable=True)


class CreatorJudgment(Base):
    """Cached Jev answers. Reused when the creator's content, the brief and the questions are unchanged."""

    __tablename__ = "creator_judgments"
    __table_args__ = (
        UniqueConstraint("creator_id", "content_hash", "brief_hash", "questions_version", name="uq_creator_judgment_key"),
    )

    judgment_id = Column(String, primary_key=True, default=_uuid)
    creator_id = Column(String, ForeignKey("creators.creator_id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    content_hash = Column(String, nullable=False)
    brief_hash = Column(String, nullable=False)
    questions_version = Column(String, nullable=False)
    model = Column(String, nullable=True)
    source = Column(String, nullable=True)  # "jev" | "llm_fallback"
    answers = Column(JSONType, nullable=False)
    input_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PersonLink(Base):
    __tablename__ = "person_links"

    creator_id = Column(String, ForeignKey("creators.creator_id", ondelete="CASCADE"), primary_key=True)
    person_id = Column(String, ForeignKey("creator_persons.person_id", ondelete="CASCADE"), nullable=False, index=True)
    link_source = Column(String, nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    status = Column(String, nullable=False, default="linked")  # "linked" | "suggested"
    verified_at = Column(DateTime(timezone=True), server_default=func.now())


class CreatorEmbedding(Base):
    __tablename__ = "creator_embeddings"
    __table_args__ = (
        Index(
            "ix_creator_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    creator_id = Column(String, ForeignKey("creators.creator_id", ondelete="CASCADE"), primary_key=True)
    model = Column(String, nullable=False)
    text_hash = Column(String, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
