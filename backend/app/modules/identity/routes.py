import hmac
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.security import csrf_token, token_digest
from app.modules.identity.models import PlatformAccount, User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import (
    AccountCreate,
    AccountRead,
    AuditRead,
    BrandCreate,
    BrandRead,
    BrandUpdate,
    GrantRead,
    Login,
    MemberGrant,
    Named,
    NicheRead,
    PermissionGrant,
    SessionRead,
    StyleGuide,
    UserRead,
    WorkspaceRead,
)
from app.modules.identity.service import IdentityService

router = APIRouter(prefix="/api", tags=["identity"])
COOKIE = "cisrice_session"
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def service(request: Request) -> Iterator[IdentityService]:
    with Session(request.app.state.engine) as database, database.begin():
        yield IdentityService(
            IdentityRepository(database), request.app.state.settings, request.state.correlation_id
        )


Service = Annotated[IdentityService, Depends(service, scope="function")]


def actor(request: Request, svc: Service) -> User:
    return svc.authenticate(request.cookies.get(COOKIE))[0]


Actor = Annotated[User, Depends(actor)]


def origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise HTTPException(403, "Trusted Origin header required")


def rate(request: Request, subject: str, limit: int, seconds: int) -> None:
    namespace = request.app.state.settings.rate_namespace
    key = f"{namespace}:{token_digest(subject)}"
    try:
        count = request.app.state.redis.eval(
            "local n=redis.call('INCR',KEYS[1]); "
            "if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
            1,
            key,
            seconds,
        )
    except RedisError:
        raise HTTPException(503, "Authentication protection temporarily unavailable") from None
    if int(count) > limit:
        raise HTTPException(
            429, "Too many requests; try again later", headers={"Retry-After": str(seconds)}
        )


def csrf_actor(request: Request, user: Actor) -> User:
    origin(request)
    token = request.cookies.get(COOKIE, "")
    if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf_token(token)):
        raise HTTPException(403, "Valid CSRF token required")
    return user


CsrfActor = Annotated[User, Depends(csrf_actor)]


def write_actor(request: Request, user: CsrfActor) -> User:
    rate(request, f"write:{user.id}", request.app.state.settings.mutation_limit, 60)
    return user


Writer = Annotated[User, Depends(write_actor)]


@router.get("/auth/status")
def auth_status(svc: Service) -> dict[str, bool]:
    return {"setup_required": not svc.repo.first_user_exists()}


@router.post("/auth/login", response_model=SessionRead)
def login(
    data: Login, request: Request, response: Response, svc: Service
) -> SessionRead | JSONResponse:
    origin(request)
    settings = request.app.state.settings
    rate(
        request,
        f"login-ip:{request.client.host if request.client else 'unknown'}",
        settings.login_ip_limit,
        900,
    )
    rate(request, f"login-email:{data.email}", settings.login_email_limit, 900)
    result = svc.login(data.email, data.password.get_secret_value(), request.cookies.get(COOKIE))
    if result is None:
        # A response, not a raised exception, commits the failed-login audit event.
        return JSONResponse({"detail": "Invalid email or password"}, status_code=401)
    response.set_cookie(
        COOKIE,
        result.token,
        max_age=settings.session_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return result.session


@router.get("/auth/session", response_model=SessionRead)
def session(request: Request, svc: Service) -> SessionRead:
    token = request.cookies.get(COOKIE)
    user, auth_session = svc.authenticate(token)
    return SessionRead(
        user=UserRead.model_validate(user),
        csrf_token=csrf_token(token or ""),
        expires_at=auth_session.expires_at,
    )


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: CsrfActor, svc: Service) -> None:
    svc.logout(user, request.cookies[COOKIE])
    response.delete_cookie(
        COOKIE,
        path="/",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.get("/workspaces", response_model=list[WorkspaceRead])
def workspaces(
    user: Actor, svc: Service, limit: Limit = 200, offset: Offset = 0
) -> list[WorkspaceRead]:
    return svc.list_workspaces(user, limit, offset)


@router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
def create_workspace(data: Named, user: Writer, svc: Service) -> WorkspaceRead:
    return svc.create_workspace(user, data.name)


@router.get("/workspaces/{workspace}/niches", response_model=list[NicheRead])
def niches(
    workspace: UUID, user: Actor, svc: Service, limit: Limit = 200, offset: Offset = 0
) -> list[NicheRead]:
    svc.require_workspace(user, workspace)
    return [NicheRead.model_validate(row) for row in svc.repo.niches(workspace, limit, offset)]


@router.post("/workspaces/{workspace}/niches", response_model=NicheRead, status_code=201)
def create_niche(workspace: UUID, data: Named, user: Writer, svc: Service) -> NicheRead:
    return NicheRead.model_validate(svc.create_niche(user, workspace, data.name))


@router.get("/workspaces/{workspace}/brands", response_model=list[BrandRead])
def brands(
    workspace: UUID, user: Actor, svc: Service, limit: Limit = 200, offset: Offset = 0
) -> list[BrandRead]:
    owner = svc.require_workspace(user, workspace) == "owner"
    return [
        svc.brand_read(row, role)
        for row, role in svc.repo.brands(workspace, user.id, owner, limit, offset)
    ]


@router.post("/workspaces/{workspace}/brands", response_model=BrandRead, status_code=201)
def create_brand(workspace: UUID, data: BrandCreate, user: Writer, svc: Service) -> BrandRead:
    return svc.create_brand(user, workspace, data)


@router.get("/workspaces/{workspace}/brands/{brand}", response_model=BrandRead)
def brand_detail(workspace: UUID, brand: UUID, user: Actor, svc: Service) -> BrandRead:
    row, role = svc.require_brand(user, workspace, brand)
    return svc.brand_read(row, role)


@router.patch("/workspaces/{workspace}/brands/{brand}", response_model=BrandRead)
def update_brand(
    workspace: UUID, brand: UUID, data: BrandUpdate, user: Writer, svc: Service
) -> BrandRead:
    return svc.update_brand(user, workspace, brand, data)


@router.get("/workspaces/{workspace}/brands/{brand}/style-guide", response_model=StyleGuide)
def style_guide(workspace: UUID, brand: UUID, user: Actor, svc: Service) -> StyleGuide:
    return svc.style(user, workspace, brand)


@router.put("/workspaces/{workspace}/brands/{brand}/style-guide", response_model=StyleGuide)
def update_style(
    workspace: UUID, brand: UUID, data: StyleGuide, user: Writer, svc: Service
) -> StyleGuide:
    return svc.update_style(user, workspace, brand, data)


@router.get("/workspaces/{workspace}/brands/{brand}/accounts", response_model=list[AccountRead])
def accounts(workspace: UUID, brand: UUID, user: Actor, svc: Service) -> list[AccountRead]:
    _, role = svc.require_brand(user, workspace, brand)
    return [
        account_read(row, user, svc)
        for row in svc.repo.accounts(workspace, brand, user.id, role == "owner")
    ]


@router.post(
    "/workspaces/{workspace}/brands/{brand}/accounts", response_model=AccountRead, status_code=201
)
def register_account(
    workspace: UUID, brand: UUID, data: AccountCreate, user: Writer, svc: Service
) -> AccountRead:
    return account_read(svc.register_account(user, workspace, brand, data), user, svc)


@router.get("/workspaces/{workspace}/brands/{brand}/accounts/{account}", response_model=AccountRead)
def account_detail(
    workspace: UUID, brand: UUID, account: UUID, user: Actor, svc: Service
) -> AccountRead:
    return account_read(svc.require_account(user, workspace, brand, account), user, svc)


@router.get("/workspaces/{workspace}/members", response_model=list[GrantRead])
def members(workspace: UUID, user: Actor, svc: Service) -> list[GrantRead]:
    svc.require_workspace(user, workspace, owner=True)
    return [
        GrantRead(user_id=row.id, email=row.email, role=role)
        for row, role in svc.repo.members(workspace)
    ]


@router.put("/workspaces/{workspace}/members", response_model=GrantRead)
def grant_member(workspace: UUID, data: MemberGrant, user: Writer, svc: Service) -> GrantRead:
    return svc.member(user, workspace, data)


@router.get("/workspaces/{workspace}/brands/{brand}/permissions", response_model=list[GrantRead])
def brand_permissions(workspace: UUID, brand: UUID, user: Actor, svc: Service) -> list[GrantRead]:
    svc.require_workspace(user, workspace, owner=True)
    svc.require_brand(user, workspace, brand)
    return [
        GrantRead(user_id=row.id, email=row.email, role=role)
        for row, role in svc.repo.brand_grants(workspace, brand)
    ]


@router.put("/workspaces/{workspace}/brands/{brand}/permissions", response_model=GrantRead)
def grant_brand(
    workspace: UUID, brand: UUID, data: PermissionGrant, user: Writer, svc: Service
) -> GrantRead:
    return svc.brand_grant(user, workspace, brand, data)


@router.get(
    "/workspaces/{workspace}/brands/{brand}/accounts/{account}/permissions",
    response_model=list[GrantRead],
)
def account_permissions(
    workspace: UUID, brand: UUID, account: UUID, user: Actor, svc: Service
) -> list[GrantRead]:
    svc.require_workspace(user, workspace, owner=True)
    svc.require_account(user, workspace, brand, account)
    return [
        GrantRead(user_id=row.id, email=row.email, role=role)
        for row, role in svc.repo.account_grants(workspace, account)
    ]


@router.put(
    "/workspaces/{workspace}/brands/{brand}/accounts/{account}/permissions",
    response_model=GrantRead,
)
def grant_account(
    workspace: UUID, brand: UUID, account: UUID, data: PermissionGrant, user: Writer, svc: Service
) -> GrantRead:
    return svc.account_grant(user, workspace, brand, account, data)


@router.get("/workspaces/{workspace}/audit", response_model=list[AuditRead])
def workspace_audit(
    workspace: UUID, user: Actor, svc: Service, limit: Limit = 100, offset: Offset = 0
) -> list[AuditRead]:
    svc.require_workspace(user, workspace, owner=True)
    return [AuditRead.model_validate(row) for row in svc.repo.audit(workspace, None, limit, offset)]


@router.get("/workspaces/{workspace}/brands/{brand}/audit", response_model=list[AuditRead])
def brand_audit(
    workspace: UUID, brand: UUID, user: Actor, svc: Service, limit: Limit = 100, offset: Offset = 0
) -> list[AuditRead]:
    svc.require_brand(user, workspace, brand)
    return [
        AuditRead.model_validate(row) for row in svc.repo.audit(workspace, brand, limit, offset)
    ]


@router.delete("/workspaces/{workspace}/members/{member}", status_code=204)
def remove_member(workspace: UUID, member: UUID, user: Writer, svc: Service) -> None:
    svc.remove_member(user, workspace, member)


@router.delete("/workspaces/{workspace}/brands/{brand}/permissions/{member}", status_code=204)
def revoke_brand(workspace: UUID, brand: UUID, member: UUID, user: Writer, svc: Service) -> None:
    svc.revoke_brand(user, workspace, brand, member)


@router.delete(
    "/workspaces/{workspace}/brands/{brand}/accounts/{account}/permissions/{member}",
    status_code=204,
)
def revoke_account(
    workspace: UUID, brand: UUID, account: UUID, member: UUID, user: Writer, svc: Service
) -> None:
    svc.revoke_account(user, workspace, brand, account, member)


@router.patch(
    "/workspaces/{workspace}/brands/{brand}/accounts/{account}", response_model=AccountRead
)
def update_account(
    workspace: UUID, brand: UUID, account: UUID, data: AccountCreate, user: Writer, svc: Service
) -> AccountRead:
    return account_read(svc.update_account(user, workspace, brand, account, data), user, svc)


def account_read(row: PlatformAccount, user: User, svc: IdentityService) -> AccountRead:
    _, role = svc.require_brand(user, row.workspace_id, row.brand_id)
    permission = svc.repo.account_permission(row.workspace_id, row.id, user.id)
    result = AccountRead.model_validate(row)
    result.can_edit = role == "owner" or (
        role == "editor" and permission is not None and permission.role == "editor"
    )
    return result
