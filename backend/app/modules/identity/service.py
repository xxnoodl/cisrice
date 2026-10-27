import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import (
    DUMMY_HASH,
    csrf_token,
    hasher,
    password_hash,
    token_digest,
    verify_password,
)
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
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import (
    AccountCreate,
    BrandCreate,
    BrandRead,
    BrandUpdate,
    GrantRead,
    MemberGrant,
    PermissionGrant,
    SessionRead,
    StyleGuide,
    UserRead,
    WorkspaceRead,
)


@dataclass
class LoginResult:
    session: SessionRead
    token: str


class IdentityService:
    def __init__(
        self, repository: IdentityRepository, settings: Settings, correlation: str
    ) -> None:
        self.repo = repository
        self.settings = settings
        self.correlation = correlation

    def record(
        self,
        actor: User | None,
        event: str,
        target: UUID | None = None,
        workspace: UUID | None = None,
        brand: UUID | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        self.repo.save(
            AuditEvent(
                actor_id=actor.id if actor else None,
                workspace_id=workspace,
                brand_id=brand,
                event_type=event,
                target_id=str(target) if target else None,
                correlation_id=self.correlation,
                details=details or {},
            )
        )

    def login(self, email: str, password: str, old_token: str | None) -> LoginResult | None:
        user = self.repo.user_by_email(email)
        valid = verify_password(user.password_hash if user else DUMMY_HASH, password)
        if not user or not valid or not user.is_active:
            self.record(None, "auth.login_failed")
            return None
        if hasher.check_needs_rehash(user.password_hash):
            user.password_hash = password_hash(password)
        if old_token:
            self.repo.revoke(token_digest(old_token))
        now = datetime.now(UTC)
        self.repo.trim_sessions(user.id, now)
        token = secrets.token_urlsafe(32)
        session = self.repo.save(
            AuthSession(
                token_hash=token_digest(token),
                user_id=user.id,
                expires_at=now + timedelta(seconds=self.settings.session_seconds),
            )
        )
        self.record(user, "auth.login")
        return LoginResult(
            SessionRead(
                user=UserRead.model_validate(user),
                csrf_token=csrf_token(token),
                expires_at=session.expires_at,
            ),
            token,
        )

    def authenticate(self, token: str | None) -> tuple[User, AuthSession]:
        found = (
            self.repo.session_user(token_digest(token), datetime.now(UTC))
            if (token and 20 <= len(token) <= 200)
            else None
        )
        if not found:
            raise HTTPException(401, "Sign in required")
        return found

    def logout(self, actor: User, token: str) -> None:
        self.repo.revoke(token_digest(token))
        self.record(actor, "auth.logout")

    def require_workspace(self, actor: User, workspace: UUID, owner: bool = False) -> str:
        membership = self.repo.membership(workspace, actor.id)
        if not membership:
            raise HTTPException(404, "Workspace not found")
        if owner and membership.role != "owner":
            raise HTTPException(403, "Workspace owner permission required")
        return membership.role

    def require_brand(
        self, actor: User, workspace: UUID, brand_id: UUID, write: bool = False
    ) -> tuple[Brand, str]:
        workspace_role = self.require_workspace(actor, workspace)
        brand = self.repo.brand(workspace, brand_id)
        if not brand:
            raise HTTPException(404, "Brand not found")
        permission = self.repo.brand_permission(workspace, brand_id, actor.id)
        role = "owner" if workspace_role == "owner" else permission.role if permission else None
        if role is None:
            raise HTTPException(404, "Brand not found")
        if write and role not in {"owner", "editor"}:
            raise HTTPException(403, "Brand editor permission required")
        return brand, role

    def require_account(
        self, actor: User, workspace: UUID, brand: UUID, account: UUID, write: bool = False
    ) -> PlatformAccount:
        _, role = self.require_brand(actor, workspace, brand, write=write)
        found = self.repo.account(workspace, brand, account)
        permission = self.repo.account_permission(workspace, account, actor.id)
        if not found or (role != "owner" and not permission):
            raise HTTPException(404, "Platform account not found")
        if write and role != "owner" and permission and permission.role != "editor":
            raise HTTPException(403, "Account editor permission required")
        return found

    def create_workspace(self, actor: User, name: str) -> WorkspaceRead:
        workspace = self.repo.save(Workspace(name=name, created_by=actor.id))
        self.repo.save(
            WorkspaceMembership(workspace_id=workspace.id, user_id=actor.id, role="owner")
        )
        self.record(actor, "workspace.created", workspace.id, workspace.id)
        return WorkspaceRead(id=workspace.id, name=name, role="owner")

    def list_workspaces(self, actor: User, limit: int, offset: int) -> list[WorkspaceRead]:
        return [
            WorkspaceRead(id=row.id, name=row.name, role=role)
            for row, role in self.repo.workspaces(actor.id, limit, offset)
        ]

    def create_niche(self, actor: User, workspace: UUID, name: str) -> Niche:
        self.require_workspace(actor, workspace, owner=True)
        niche = self.repo.save(Niche(workspace_id=workspace, name=name))
        self.record(actor, "niche.created", niche.id, workspace)
        return niche

    def create_brand(self, actor: User, workspace: UUID, data: BrandCreate) -> BrandRead:
        self.require_workspace(actor, workspace, owner=True)
        if not self.repo.niche(workspace, data.niche_id):
            raise HTTPException(404, "Niche not found")
        brand = self.repo.save(Brand(workspace_id=workspace, **data.model_dump()))
        self.repo.save(BrandStyleGuide(brand_id=brand.id))
        self.record(actor, "brand.created", brand.id, workspace, brand.id)
        return self.brand_read(brand, "owner")

    @staticmethod
    def brand_read(brand: Brand, role: str) -> BrandRead:
        return BrandRead(
            id=brand.id,
            workspace_id=brand.workspace_id,
            niche_id=brand.niche_id,
            name=brand.name,
            description=brand.description,
            role=role,
        )

    def update_brand(
        self, actor: User, workspace: UUID, brand_id: UUID, data: BrandUpdate
    ) -> BrandRead:
        brand, role = self.require_brand(actor, workspace, brand_id, write=True)
        brand.name, brand.description = data.name, data.description
        self.repo.save(brand)
        self.record(actor, "brand.updated", brand.id, workspace, brand.id)
        return self.brand_read(brand, role)

    def style(self, actor: User, workspace: UUID, brand: UUID) -> StyleGuide:
        self.require_brand(actor, workspace, brand)
        row = self.repo.style(brand)
        if row is None:
            raise HTTPException(404, "Style guide not found")
        return StyleGuide(
            voice=row.voice, audience=row.audience, typography=row.typography, colors=row.colors
        )

    def update_style(
        self, actor: User, workspace: UUID, brand: UUID, data: StyleGuide
    ) -> StyleGuide:
        self.require_brand(actor, workspace, brand, write=True)
        row = self.repo.style(brand)
        if row is None:
            raise HTTPException(404, "Style guide not found")
        row.voice, row.audience, row.typography, row.colors = (
            data.voice,
            data.audience,
            data.typography,
            data.colors,
        )
        self.repo.save(row)
        self.record(actor, "brand.style_updated", brand, workspace, brand)
        return data

    def register_account(
        self, actor: User, workspace: UUID, brand: UUID, data: AccountCreate
    ) -> PlatformAccount:
        self.require_brand(actor, workspace, brand, write=True)
        account = self.repo.save(
            PlatformAccount(workspace_id=workspace, brand_id=brand, **data.model_dump())
        )
        # Brand editors receive explicit access to accounts they register.
        if self.require_workspace(actor, workspace) != "owner":
            self.repo.save(
                AccountPermission(
                    workspace_id=workspace, account_id=account.id, user_id=actor.id, role="editor"
                )
            )
        self.record(actor, "account.registered", account.id, workspace, brand)
        return account

    def member(self, actor: User, workspace: UUID, data: MemberGrant) -> GrantRead:
        self.require_workspace(actor, workspace, owner=True)
        self.repo.workspace(workspace, lock=True)
        self.require_workspace(actor, workspace, owner=True)
        user = self.repo.user_by_email(data.email)
        if not user or not user.is_active:
            raise HTTPException(404, "Active user not found")
        existing = self.repo.membership(workspace, user.id)
        owners = sum(role == "owner" for _, role in self.repo.members(workspace))
        if existing and existing.role == "owner" and data.role != "owner" and owners <= 1:
            raise HTTPException(409, "A workspace must retain an owner")
        if existing:
            existing.role = data.role
            self.repo.save(existing)
        else:
            self.repo.save(
                WorkspaceMembership(workspace_id=workspace, user_id=user.id, role=data.role)
            )
        self.record(actor, "membership.changed", user.id, workspace, details={"role": data.role})
        return GrantRead(user_id=user.id, email=user.email, role=data.role)

    def brand_grant(
        self, actor: User, workspace: UUID, brand: UUID, data: PermissionGrant
    ) -> GrantRead:
        self.require_workspace(actor, workspace, owner=True)
        self.require_brand(actor, workspace, brand)
        user = self.repo.user_by_email(data.email)
        if not user or not self.repo.membership(workspace, user.id):
            raise HTTPException(404, "Workspace member not found")
        permission = self.repo.brand_permission(workspace, brand, user.id)
        if permission:
            permission.role = data.role
            self.repo.save(permission)
        else:
            self.repo.save(
                BrandPermission(
                    workspace_id=workspace, brand_id=brand, user_id=user.id, role=data.role
                )
            )
        self.record(
            actor,
            "brand.permission_changed",
            user.id,
            workspace,
            brand,
            details={"role": data.role},
        )
        return GrantRead(user_id=user.id, email=user.email, role=data.role)

    def account_grant(
        self, actor: User, workspace: UUID, brand: UUID, account: UUID, data: PermissionGrant
    ) -> GrantRead:
        self.require_workspace(actor, workspace, owner=True)
        self.require_account(actor, workspace, brand, account)
        user = self.repo.user_by_email(data.email)
        if not user or not self.repo.membership(workspace, user.id):
            raise HTTPException(404, "Workspace member not found")
        if not self.repo.brand_permission(workspace, brand, user.id) and (
            self.require_workspace(user, workspace) != "owner"
        ):
            raise HTTPException(409, "Grant brand access before granting account access")
        permission = self.repo.account_permission(workspace, account, user.id)
        if permission:
            permission.role = data.role
            self.repo.save(permission)
        else:
            self.repo.save(
                AccountPermission(
                    workspace_id=workspace, account_id=account, user_id=user.id, role=data.role
                )
            )
        self.record(
            actor,
            "account.permission_changed",
            user.id,
            workspace,
            brand,
            details={"role": data.role, "account_id": str(account)},
        )
        return GrantRead(user_id=user.id, email=user.email, role=data.role)

    def remove_member(self, actor: User, workspace: UUID, user: UUID) -> None:
        self.require_workspace(actor, workspace, owner=True)
        self.repo.workspace(workspace, lock=True)
        self.require_workspace(actor, workspace, owner=True)
        member = self.repo.membership(workspace, user)
        if not member:
            raise HTTPException(404, "Workspace member not found")
        if (
            member.role == "owner"
            and sum(role == "owner" for _, role in self.repo.members(workspace)) <= 1
        ):
            raise HTTPException(409, "A workspace must retain an owner")
        self.repo.remove_member(workspace, user)
        self.record(actor, "membership.removed", user, workspace)

    def revoke_brand(self, actor: User, workspace: UUID, brand: UUID, user: UUID) -> None:
        self.require_workspace(actor, workspace, owner=True)
        self.require_brand(actor, workspace, brand)
        self.repo.revoke_brand(workspace, brand, user)
        self.record(actor, "brand.permission_revoked", user, workspace, brand)

    def revoke_account(
        self, actor: User, workspace: UUID, brand: UUID, account: UUID, user: UUID
    ) -> None:
        self.require_workspace(actor, workspace, owner=True)
        self.require_account(actor, workspace, brand, account)
        self.repo.revoke_account(workspace, account, user)
        self.record(
            actor,
            "account.permission_revoked",
            user,
            workspace,
            brand,
            details={"account_id": str(account)},
        )

    def update_account(
        self, actor: User, workspace: UUID, brand: UUID, account: UUID, data: AccountCreate
    ) -> PlatformAccount:
        row = self.require_account(actor, workspace, brand, account, write=True)
        if row.platform != data.platform:
            raise HTTPException(422, "A registered account's platform cannot be changed")
        row.handle, row.display_name, row.profile_url, row.timezone = (
            data.handle,
            data.display_name,
            data.profile_url,
            data.timezone,
        )
        self.repo.save(row)
        self.record(actor, "account.updated", row.id, workspace, brand)
        return row
