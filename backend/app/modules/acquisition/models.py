from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RightsDecision(Base):
    __tablename__ = "rights_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id"], ["brands.workspace_id", "brands.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "brand_id", "candidate_id"],
            [
                "discovery_candidates.workspace_id",
                "discovery_candidates.brand_id",
                "discovery_candidates.id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "brand_id", "id", name="uq_rights_scope"),
        CheckConstraint("status IN ('APPROVED','REVOKED')", name="ck_rights_status"),
        CheckConstraint("basis IN ('OWNED','LICENSED','PERMISSION')", name="ck_rights_basis"),
        CheckConstraint("adapter IN ('direct','ytdlp')", name="ck_acquisition_adapter"),
        Index("ix_rights_scope_created", "workspace_id", "brand_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column()
    brand_id: Mapped[UUID] = mapped_column()
    candidate_id: Mapped[UUID | None] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(2048))
    adapter: Mapped[str] = mapped_column(String(16))
    basis: Mapped[str] = mapped_column(String(16))
    license: Mapped[str] = mapped_column(String(300))
    evidence: Mapped[str] = mapped_column(Text)
    attribution: Mapped[str] = mapped_column(Text)
    restrictions: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="APPROVED")
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaObject(Base):
    __tablename__ = "media_objects"
    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0 AND duration > 0 AND width > 0 AND height > 0",
            name="ck_media_dimensions",
        ),
    )
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    extension: Mapped[str] = mapped_column(String(8))
    mime: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column()
    duration: Mapped[float] = mapped_column()
    width: Mapped[int] = mapped_column()
    height: Mapped[int] = mapped_column()
    video_codec: Mapped[str] = mapped_column(String(80))
    audio_codec: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BrandAsset(Base):
    __tablename__ = "brand_assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id", "rights_id"],
            ["rights_decisions.workspace_id", "rights_decisions.brand_id", "rights_decisions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "brand_id", "job_id"],
            ["durable_jobs.workspace_id", "durable_jobs.brand_id", "durable_jobs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("job_id", name="uq_asset_job"),
        UniqueConstraint("brand_id", "rights_id", "sha256", name="uq_brand_asset_rights"),
        Index("ix_asset_scope_created", "workspace_id", "brand_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column()
    brand_id: Mapped[UUID] = mapped_column()
    rights_id: Mapped[UUID] = mapped_column()
    job_id: Mapped[UUID | None] = mapped_column()
    sha256: Mapped[str] = mapped_column(ForeignKey("media_objects.sha256", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    export_name: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
