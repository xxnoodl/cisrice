from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (CheckConstraint("role IN ('owner', 'member')", name="ck_membership_role"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16))


class Niche(Base):
    __tablename__ = "niches"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_niche_name"),
        UniqueConstraint("workspace_id", "id", name="uq_niche_scope"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))


class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "niche_id"], ["niches.workspace_id", "niches.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("workspace_id", "id", name="uq_brand_scope"),
        UniqueConstraint("workspace_id", "name", name="uq_brand_name"),
        Index("ix_brand_niche", "workspace_id", "niche_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    niche_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BrandStyleGuide(Base):
    __tablename__ = "brand_style_guides"
    brand_id: Mapped[UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), primary_key=True
    )
    voice: Mapped[str] = mapped_column(Text, default="", server_default="")
    audience: Mapped[str] = mapped_column(Text, default="", server_default="")
    typography: Mapped[str] = mapped_column(String(120), default="", server_default="")
    colors: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )


class BrandPermission(Base):
    __tablename__ = "brand_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id"], ["brands.workspace_id", "brands.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "user_id"],
            ["workspace_memberships.workspace_id", "workspace_memberships.user_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("role IN ('editor', 'viewer')", name="ck_brand_permission_role"),
    )
    brand_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    role: Mapped[str] = mapped_column(String(16))


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "brand_id"], ["brands.workspace_id", "brands.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("workspace_id", "id", name="uq_account_scope"),
        UniqueConstraint("brand_id", "platform", "handle", name="uq_account_identity"),
        CheckConstraint(
            "platform IN ('youtube','instagram','facebook','tiktok','x')",
            name="ck_account_platform",
        ),
        CheckConstraint(
            "connection_status IN ('REGISTERED','CONNECTED','NEEDS_AUTHORIZATION',"
            "'EXPIRED','RESTRICTED','DISCONNECTED')",
            name="ck_account_status",
        ),
        Index("ix_account_brand", "workspace_id", "brand_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column()
    brand_id: Mapped[UUID] = mapped_column()
    platform: Mapped[str] = mapped_column(String(24))
    handle: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    profile_url: Mapped[str] = mapped_column(String(2048), default="", server_default="")
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", server_default="UTC")
    connection_status: Mapped[str] = mapped_column(
        String(24), default="REGISTERED", server_default="REGISTERED"
    )


class AccountPermission(Base):
    __tablename__ = "account_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "account_id"],
            ["platform_accounts.workspace_id", "platform_accounts.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "user_id"],
            ["workspace_memberships.workspace_id", "workspace_memberships.user_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("role IN ('editor', 'viewer')", name="ck_account_permission_role"),
    )
    account_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    role: Mapped[str] = mapped_column(String(16))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_workspace_time", "workspace_id", "created_at"),
        Index("ix_audit_brand_time", "brand_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL")
    )
    brand_id: Mapped[UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(36))
    details: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
