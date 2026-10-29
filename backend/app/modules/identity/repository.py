from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.modules.identity.models import (
    AccountPermission,
    AuditEvent,
    AuthSession,
    Brand,
    BrandPermission,
    BrandStyleGuide,
    Niche,
    PlatformAccount,
    User,
    Workspace,
    WorkspaceMembership,
)


class IdentityRepository:
    def user_by_id(self, identifier: UUID) -> User | None:
        return self.db.get(User, identifier, populate_existing=True)

    def __init__(self, session: Session) -> None:
        self.db = session

    def save[T: Base](self, row: T) -> T:
        self.db.add(row)
        self.db.flush()
        return row

    def user_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def first_user_exists(self) -> bool:
        return self.db.scalar(select(User.id).limit(1)) is not None

    def session_user(self, digest: str, now: datetime) -> tuple[User, AuthSession] | None:
        row = self.db.execute(
            select(User, AuthSession)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(
                AuthSession.token_hash == digest,
                AuthSession.expires_at > now,
                User.is_active.is_(True),
            )
        ).one_or_none()
        return (row[0], row[1]) if row else None

    def revoke(self, digest: str) -> None:
        self.db.execute(delete(AuthSession).where(AuthSession.token_hash == digest))

    def trim_sessions(self, user_id: UUID, now: datetime) -> None:
        self.db.execute(
            delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.expires_at <= now)
        )
        tokens = list(
            self.db.scalars(
                select(AuthSession.token_hash)
                .where(AuthSession.user_id == user_id)
                .order_by(AuthSession.created_at.desc())
                .offset(4)
            )
        )
        if tokens:
            self.db.execute(delete(AuthSession).where(AuthSession.token_hash.in_(tokens)))

    def membership(self, workspace: UUID, user: UUID) -> WorkspaceMembership | None:
        return self.db.scalar(
            select(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == workspace, WorkspaceMembership.user_id == user
            )
            .execution_options(populate_existing=True)
        )

    def workspaces(self, user: UUID, limit: int, offset: int) -> list[tuple[Workspace, str]]:
        rows = self.db.execute(
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == user)
            .order_by(Workspace.name, Workspace.id)
            .limit(limit)
            .offset(offset)
        )
        return [(row[0], row[1]) for row in rows]

    def workspace(self, workspace: UUID, lock: bool = False) -> Workspace | None:
        statement = select(Workspace).where(Workspace.id == workspace)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def members(self, workspace: UUID) -> list[tuple[User, str]]:
        rows = self.db.execute(
            select(User, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(WorkspaceMembership.workspace_id == workspace)
            .order_by(User.email)
        )
        return [(row[0], row[1]) for row in rows]

    def niches(self, workspace: UUID, limit: int, offset: int) -> list[Niche]:
        return list(
            self.db.scalars(
                select(Niche)
                .where(Niche.workspace_id == workspace)
                .order_by(Niche.name, Niche.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def niche(self, workspace: UUID, niche: UUID) -> Niche | None:
        return self.db.scalar(
            select(Niche).where(Niche.workspace_id == workspace, Niche.id == niche)
        )

    def brand(self, workspace: UUID, brand: UUID) -> Brand | None:
        return self.db.scalar(
            select(Brand).where(Brand.workspace_id == workspace, Brand.id == brand)
        )

    def brands(
        self, workspace: UUID, user: UUID, owner: bool, limit: int, offset: int
    ) -> list[tuple[Brand, str]]:
        if owner:
            brands = self.db.scalars(
                select(Brand)
                .where(Brand.workspace_id == workspace)
                .order_by(Brand.name, Brand.id)
                .limit(limit)
                .offset(offset)
            )
            return [(brand, "owner") for brand in brands]
        rows = self.db.execute(
            select(Brand, BrandPermission.role)
            .join(BrandPermission, BrandPermission.brand_id == Brand.id)
            .where(
                Brand.workspace_id == workspace,
                BrandPermission.workspace_id == workspace,
                BrandPermission.user_id == user,
            )
            .order_by(Brand.name, Brand.id)
            .limit(limit)
            .offset(offset)
        )
        return [(row[0], row[1]) for row in rows]

    def brand_permission(self, workspace: UUID, brand: UUID, user: UUID) -> BrandPermission | None:
        return self.db.scalar(
            select(BrandPermission).where(
                BrandPermission.workspace_id == workspace,
                BrandPermission.brand_id == brand,
                BrandPermission.user_id == user,
            )
        )

    def brand_grants(self, workspace: UUID, brand: UUID) -> list[tuple[User, str]]:
        rows = self.db.execute(
            select(User, BrandPermission.role)
            .join(BrandPermission, BrandPermission.user_id == User.id)
            .where(BrandPermission.workspace_id == workspace, BrandPermission.brand_id == brand)
            .order_by(User.email)
        )
        return [(row[0], row[1]) for row in rows]

    def style(self, brand: UUID) -> BrandStyleGuide | None:
        return self.db.get(BrandStyleGuide, brand)

    def account(self, workspace: UUID, brand: UUID, account: UUID) -> PlatformAccount | None:
        return self.db.scalar(
            select(PlatformAccount).where(
                PlatformAccount.workspace_id == workspace,
                PlatformAccount.brand_id == brand,
                PlatformAccount.id == account,
            )
        )

    def accounts(
        self, workspace: UUID, brand: UUID, user: UUID, owner: bool
    ) -> list[PlatformAccount]:
        statement = select(PlatformAccount).where(
            PlatformAccount.workspace_id == workspace, PlatformAccount.brand_id == brand
        )
        if not owner:
            statement = statement.join(
                AccountPermission, AccountPermission.account_id == PlatformAccount.id
            ).where(AccountPermission.workspace_id == workspace, AccountPermission.user_id == user)
        return list(
            self.db.scalars(statement.order_by(PlatformAccount.platform, PlatformAccount.handle))
        )

    def account_permission(
        self, workspace: UUID, account: UUID, user: UUID
    ) -> AccountPermission | None:
        return self.db.scalar(
            select(AccountPermission).where(
                AccountPermission.workspace_id == workspace,
                AccountPermission.account_id == account,
                AccountPermission.user_id == user,
            )
        )

    def account_grants(self, workspace: UUID, account: UUID) -> list[tuple[User, str]]:
        rows = self.db.execute(
            select(User, AccountPermission.role)
            .join(AccountPermission, AccountPermission.user_id == User.id)
            .where(
                AccountPermission.workspace_id == workspace, AccountPermission.account_id == account
            )
            .order_by(User.email)
        )
        return [(row[0], row[1]) for row in rows]

    def audit(
        self, workspace: UUID, brand: UUID | None, limit: int, offset: int
    ) -> list[AuditEvent]:
        statement = select(AuditEvent).where(AuditEvent.workspace_id == workspace)
        if brand is not None:
            statement = statement.where(AuditEvent.brand_id == brand)
        return list(
            self.db.scalars(
                statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def remove_member(self, workspace: UUID, user: UUID) -> None:
        self.db.execute(
            delete(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace, WorkspaceMembership.user_id == user
            )
        )

    def revoke_brand(self, workspace: UUID, brand: UUID, user: UUID) -> None:
        accounts = select(PlatformAccount.id).where(
            PlatformAccount.workspace_id == workspace, PlatformAccount.brand_id == brand
        )
        self.db.execute(
            delete(AccountPermission).where(
                AccountPermission.workspace_id == workspace,
                AccountPermission.user_id == user,
                AccountPermission.account_id.in_(accounts),
            )
        )
        self.db.execute(
            delete(BrandPermission).where(
                BrandPermission.workspace_id == workspace,
                BrandPermission.brand_id == brand,
                BrandPermission.user_id == user,
            )
        )

    def revoke_account(self, workspace: UUID, account: UUID, user: UUID) -> None:
        self.db.execute(
            delete(AccountPermission).where(
                AccountPermission.workspace_id == workspace,
                AccountPermission.account_id == account,
                AccountPermission.user_id == user,
            )
        )
