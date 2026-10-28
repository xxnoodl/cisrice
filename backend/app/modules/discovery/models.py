from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Source(Base):
    __tablename__ = "discovery_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id"], ["brands.workspace_id", "brands.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("workspace_id", "brand_id", "id", name="uq_source_scope"),
        UniqueConstraint("brand_id", "url", name="uq_source_url"),
        CheckConstraint("kind IN ('rss', 'youtube')", name="ck_source_kind"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    brand_id: Mapped[UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))
    url: Mapped[str] = mapped_column(String(2048))
    keywords: Mapped[list[str]] = mapped_column(JSONB)
    quality: Mapped[float] = mapped_column()
    weights: Mapped[dict[str, float]] = mapped_column(JSONB)
    policy_note: Mapped[str] = mapped_column(String(1000))
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id", "source_id"],
            [
                "discovery_sources.workspace_id",
                "discovery_sources.brand_id",
                "discovery_sources.id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("state IN ('SUCCEEDED', 'FAILED')", name="ck_discovery_run_state"),
        Index("ix_run_scope_time", "brand_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column()
    brand_id: Mapped[UUID] = mapped_column()
    source_id: Mapped[UUID] = mapped_column()
    state: Mapped[str] = mapped_column(String(16))
    error: Mapped[str] = mapped_column(String(500), default="")
    found: Mapped[int] = mapped_column(default=0)
    added: Mapped[int] = mapped_column(default=0)
    duplicates: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Candidate(Base):
    __tablename__ = "discovery_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id"], ["brands.workspace_id", "brands.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("workspace_id", "brand_id", "id", name="uq_candidate_scope"),
        UniqueConstraint("brand_id", "url_hash", name="uq_candidate_url"),
        CheckConstraint("status IN ('INBOX', 'APPROVED', 'REJECTED')", name="ck_candidate_status"),
        Index("ix_candidate_inbox", "brand_id", "status", "discovered_at"),
        Index("ix_candidate_title", "brand_id", "title_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column()
    brand_id: Mapped[UUID] = mapped_column()
    original_url: Mapped[str] = mapped_column(String(2048))
    url_hash: Mapped[str] = mapped_column(String(64))
    title_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(1000))
    summary: Mapped[str] = mapped_column(Text)
    topics: Mapped[list[str]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(16), default="INBOX")
    notes: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column()
    components: Mapped[dict[str, float | None]] = mapped_column(JSONB)


class Observation(Base):
    __tablename__ = "source_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id", "candidate_id"],
            [
                "discovery_candidates.workspace_id",
                "discovery_candidates.brand_id",
                "discovery_candidates.id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "brand_id", "source_id"],
            [
                "discovery_sources.workspace_id",
                "discovery_sources.brand_id",
                "discovery_sources.id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "candidate_id", "source_id", "source_identifier", name="uq_source_observation"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column()
    brand_id: Mapped[UUID] = mapped_column()
    candidate_id: Mapped[UUID] = mapped_column()
    source_id: Mapped[UUID] = mapped_column()
    source_identifier: Mapped[str] = mapped_column(String(2048))
    original_url: Mapped[str] = mapped_column(String(2048))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
