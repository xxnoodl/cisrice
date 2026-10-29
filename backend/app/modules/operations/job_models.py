from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Standalone dispatchers must register the tables referenced by these foreign keys.
from app.modules.identity import models as identity_models  # noqa: F401


class DurableJob(Base):
    __tablename__ = "durable_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id"], ["brands.workspace_id", "brands.id"], ondelete="RESTRICT"
        ),
        UniqueConstraint("brand_id", "job_type", "idempotency_key", name="uq_job_idempotency"),
        UniqueConstraint("workspace_id", "brand_id", "id", name="uq_job_scope"),
        CheckConstraint(
            "state IN ('QUEUED','RUNNING','RETRY','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_job_state",
        ),
        CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts AND max_attempts BETWEEN 1 AND 5",
            name="ck_job_attempts",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_job_progress"),
        Index("ix_job_dispatch", "state", "next_attempt_at", "next_dispatch_at"),
        Index("ix_job_scope_created", "workspace_id", "brand_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column()
    brand_id: Mapped[UUID] = mapped_column()
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    job_type: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[int] = mapped_column(default=1)
    correlation_id: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, str]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16), default="QUEUED")
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    progress: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str] = mapped_column(String(80), default="")
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    next_dispatch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
