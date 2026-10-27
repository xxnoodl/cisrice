import os
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import make_engine
from app.core.security import password_hash, token_digest
from app.main import create_app
from app.modules.identity.models import AuditEvent, AuthSession, Brand, User

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("CISRICE_INTEGRATION") != "1", reason="real services not enabled"),
]
PASSWORD = "fixture-only-long-password"
ORIGIN = "http://localhost:8080"


@dataclass
class Harness:
    clients: dict[str, TestClient]
    emails: dict[str, str]
    users: dict[str, User]
    engine: Engine
    settings: Settings

    def login(self, name: str = "owner") -> dict[str, str]:
        response = self.clients[name].post(
            "/api/auth/login", json={"email": self.emails[name], "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.fixture
def h() -> Any:
    namespace = "cisrice-test-" + uuid4().hex
    settings = Settings(
        rate_namespace=namespace, login_ip_limit=1000, login_email_limit=1000, mutation_limit=1000
    )
    engine = make_engine(settings)
    emails = {name: f"{name}-{uuid4().hex}@example.test" for name in ("owner", "member", "other")}
    users = {}
    with Session(engine, expire_on_commit=False) as db, db.begin():
        for name, email in emails.items():
            user = User(email=email, password_hash=password_hash(PASSWORD))
            db.add(user)
            users[name] = user
        db.flush()
    try:
        with ExitStack() as stack:
            clients = {
                name: stack.enter_context(
                    TestClient(
                        create_app(settings),
                        base_url="http://localhost",
                        headers={"Origin": ORIGIN},
                    )
                )
                for name in emails
            }
            yield Harness(clients, emails, users, engine, settings)
    finally:
        cache = Redis.from_url(settings.redis_url)
        keys = list(cache.scan_iter(match=namespace + ":*"))
        if keys:
            cache.delete(*keys)
        cache.close()
        engine.dispose()


def flow(client: TestClient, headers: dict[str, str]) -> tuple[str, str, str, str]:
    def post(path: str, data: dict[str, object]) -> dict[str, Any]:
        response = client.post(path, headers=headers, json=data)
        assert response.status_code == 201, response.text
        return response.json()

    w = post("/api/workspaces", {"name": "Portfolio " + uuid4().hex})
    root = f"/api/workspaces/{w['id']}"
    n = post(root + "/niches", {"name": "Technology"})
    b = post(root + "/brands", {"name": "Brand", "niche_id": n["id"]})
    a = post(root + f"/brands/{b['id']}/accounts", {"platform": "youtube", "handle": "@fixture"})
    assert a["connection_status"] == "REGISTERED"
    return w["id"], n["id"], b["id"], a["id"]


def test_portfolio_round_trip_style_and_observed_audit(h: Harness) -> None:
    headers = h.login()
    client = h.clients["owner"]
    workspace, niche, brand, account = flow(client, headers)
    root = f"/api/workspaces/{workspace}"
    path = root + f"/brands/{brand}"
    assert client.get("/api/workspaces").json()[0]["role"] == "owner"
    assert client.get(root + "/niches").json()[0]["id"] == niche
    assert client.get(root + "/brands").json()[0]["id"] == brand
    assert client.get(path + "/accounts").json()[0]["id"] == account
    style = {"voice": "Clear", "audience": "Creators", "typography": "Sans", "colors": ["#112233"]}
    assert client.put(path + "/style-guide", headers=headers, json=style).json() == style
    assert client.get(path + "/style-guide").json() == style
    assert (
        client.patch(
            path, headers=headers, json={"name": "Updated", "description": "Independent"}
        ).status_code
        == 200
    )
    audit = client.get(root + "/audit").json()
    events = {item["event_type"] for item in audit}
    assert {
        "workspace.created",
        "niche.created",
        "brand.created",
        "account.registered",
        "brand.updated",
        "brand.style_updated",
    } <= events
    assert all(item["workspace_id"] == workspace for item in audit)
    assert PASSWORD not in str(audit)
    duplicate = client.post(root + "/niches", headers=headers, json={"name": "Technology"})
    assert duplicate.status_code == 409
    assert "INSERT" not in duplicate.text


def test_workspace_brand_account_isolation_and_revocation(h: Harness) -> None:
    owner_headers = h.login()
    member_headers = h.login("member")
    other_headers = h.login("other")
    owner, member, other = (h.clients[name] for name in ("owner", "member", "other"))
    w, _, b, a = flow(owner, owner_headers)
    foreign_w, foreign_n, foreign_b, _ = flow(other, other_headers)
    root = f"/api/workspaces/{w}"
    brand = root + f"/brands/{b}"
    account = brand + f"/accounts/{a}"
    assert member.get(root + "/brands").status_code == 404
    assert owner.get(f"/api/workspaces/{foreign_w}/brands/{foreign_b}").status_code == 404
    assert (
        owner.post(
            root + "/brands",
            headers=owner_headers,
            json={"name": "Cross scope", "niche_id": foreign_n},
        ).status_code
        == 404
    )
    assert (
        owner.put(
            root + "/members",
            headers=owner_headers,
            json={"email": h.emails["member"], "role": "member"},
        ).status_code
        == 200
    )
    assert member.get(root + "/brands").json() == []
    assert member.get(brand).status_code == 404
    assert member.get(root + "/audit").status_code == 403
    assert (
        member.put(
            root + "/members",
            headers=member_headers,
            json={"email": h.emails["member"], "role": "owner"},
        ).status_code
        == 403
    )
    assert (
        owner.put(
            brand + "/permissions",
            headers=owner_headers,
            json={"email": h.emails["member"], "role": "viewer"},
        ).status_code
        == 200
    )
    assert member.get(brand).status_code == 200
    assert (
        member.patch(brand, headers=member_headers, json={"name": "Forbidden"}).status_code == 403
    )
    assert member.get(brand + "/accounts").json() == []
    assert member.get(account).status_code == 404
    assert (
        owner.put(
            account + "/permissions",
            headers=owner_headers,
            json={"email": h.emails["member"], "role": "viewer"},
        ).status_code
        == 200
    )
    assert member.get(account).status_code == 200
    assert member.get(f"/api/workspaces/{foreign_w}/brands/{b}").status_code == 404
    assert member.get(f"/api/workspaces/{w}/brands/{foreign_b}/accounts/{a}").status_code == 404
    assert member.get(brand + "/audit").status_code == 200
    for grant in (brand, account):
        assert (
            owner.put(
                grant + "/permissions",
                headers=owner_headers,
                json={"email": h.emails["member"], "role": "editor"},
            ).status_code
            == 200
        )
    assert (
        member.patch(
            account, headers=member_headers, json={"platform": "youtube", "handle": "@changed"}
        ).status_code
        == 200
    )
    assert (
        owner.delete(
            account + f"/permissions/{h.users['member'].id}", headers=owner_headers
        ).status_code
        == 204
    )
    assert member.get(account).status_code == 404
    owner.put(
        account + "/permissions",
        headers=owner_headers,
        json={"email": h.emails["member"], "role": "editor"},
    )
    assert (
        owner.delete(
            brand + f"/permissions/{h.users['member'].id}", headers=owner_headers
        ).status_code
        == 204
    )
    assert member.get(brand).status_code == 404
    owner.put(
        brand + "/permissions",
        headers=owner_headers,
        json={"email": h.emails["member"], "role": "editor"},
    )
    assert member.get(account).status_code == 404, (
        "Revoked brand must not resurrect old account grants"
    )
    assert (
        owner.delete(root + f"/members/{h.users['member'].id}", headers=owner_headers).status_code
        == 204
    )
    assert member.get(root + "/brands").status_code == 404


def test_cookie_csrf_rotation_logout_expiration_and_validation_redaction(h: Harness) -> None:
    client = h.clients["owner"]
    assert client.get("/api/workspaces").status_code == 401
    invalid = client.post(
        "/api/auth/login", json={"email": h.emails["owner"], "password": "secret"}
    )
    assert invalid.status_code == 422 and '"secret"' not in invalid.text
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": "https://evil.example"},
            json={"email": h.emails["owner"], "password": PASSWORD},
        ).status_code
        == 403
    )
    headers = h.login()
    old = client.cookies.get("cisrice_session")
    login_response = client.post(
        "/api/auth/login", json={"email": h.emails["owner"], "password": PASSWORD}
    )
    cookie = login_response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    assert (
        client.get("/api/auth/session", headers={"Cookie": f"cisrice_session={old}"}).status_code
        == 401
    )
    headers = {"X-CSRF-Token": login_response.json()["csrf_token"]}
    assert client.post("/api/workspaces", json={"name": "No csrf"}).status_code == 403
    assert (
        client.post(
            "/api/workspaces",
            headers={**headers, "Origin": "https://evil.example"},
            json={"name": "No origin"},
        ).status_code
        == 403
    )
    assert (
        client.post("/api/workspaces", headers=headers, json={"name": "Valid"}).status_code == 201
    )
    assert client.get("/api/health/live", headers={"Host": "evil.example"}).status_code == 400
    assert client.post("/api/auth/login", content=b"x" * 65537).status_code == 413
    with h.engine.begin() as db:
        rows = db.execute(
            select(AuthSession.token_hash).where(AuthSession.user_id == h.users["owner"].id)
        ).all()
        assert rows and all(row[0] != client.cookies.get("cisrice_session") for row in rows)
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/session").status_code == 401
    h.login()
    digest = token_digest(client.cookies["cisrice_session"])
    with h.engine.begin() as db:
        db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == digest)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    assert client.get("/api/auth/session").status_code == 401


def test_last_owner_and_composite_foreign_keys(h: Harness) -> None:
    headers = h.login()
    c = h.clients["owner"]
    w, _, _, _ = flow(c, headers)
    second_w, second_n, _, _ = flow(c, headers)
    root = f"/api/workspaces/{w}"
    assert (
        c.put(
            root + "/members", headers=headers, json={"email": h.emails["owner"], "role": "member"}
        ).status_code
        == 409
    )
    assert c.delete(root + f"/members/{h.users['owner'].id}", headers=headers).status_code == 409
    with pytest.raises(IntegrityError), h.engine.begin() as db:
        db.execute(insert(Brand).values(workspace_id=w, niche_id=second_n, name="Wrong tenant"))
    assert second_w != w


def test_rate_limit_and_redis_failure_are_closed(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = h.clients["owner"]
    h.settings.login_email_limit = 1
    data = {"email": h.emails["owner"], "password": "incorrect-long-password"}
    assert c.post("/api/auth/login", json=data).status_code == 401
    assert c.post("/api/auth/login", json=data).status_code == 429
    h.settings.login_email_limit = 1000
    headers = h.login()

    def unavailable(*args: object, **kwargs: object) -> None:
        raise RedisConnectionError("fixture outage")

    monkeypatch.setattr(c.app.state.redis, "eval", unavailable)
    assert c.post("/api/auth/login", json=data).status_code == 503
    assert c.post("/api/workspaces", headers=headers, json={"name": "Blocked"}).status_code == 503
    assert c.post("/api/auth/logout", headers=headers).status_code == 204
    assert c.get("/api/auth/session").status_code == 401
    with h.engine.connect() as db:
        assert db.execute(
            select(AuditEvent.id).where(AuditEvent.event_type == "auth.login_failed")
        ).first()


def test_runtime_database_role_cannot_manage_schema_or_rewrite_audit(h: Harness) -> None:
    with h.engine.connect() as db:
        row = db.execute(
            text(
                "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles "
                "WHERE rolname=current_user"
            )
        ).one()
        assert row[0] == "cisrice_app"
        assert row[1:] == (False, False, False)
    for statement in (
        "CREATE TABLE unauthorized_table (id int)",
        "UPDATE audit_events SET event_type=event_type WHERE false",
        "DELETE FROM audit_events WHERE false",
    ):
        with pytest.raises(ProgrammingError), h.engine.begin() as db:
            db.execute(text(statement))


def test_local_operator_cli_creates_real_hashed_user(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from app.core.security import verify_password
    from app.modules.identity import cli

    email = "operator-created-" + uuid4().hex + "@example.test"
    monkeypatch.setattr(sys, "argv", ["cli", "create-user", "--email", email])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: PASSWORD)
    cli.main()
    with Session(h.engine) as database:
        user = database.scalar(select(User).where(User.email == email))
        assert user is not None and verify_password(user.password_hash, PASSWORD)
        assert user.password_hash != PASSWORD
    with pytest.raises(SystemExit):
        cli.main()


def test_missing_origin_and_chunked_body_limit(h: Harness) -> None:
    client = h.clients["owner"]
    request = client.build_request(
        "POST", "/api/auth/login", json={"email": h.emails["owner"], "password": PASSWORD}
    )
    del request.headers["origin"]
    assert client.send(request).status_code == 403
    assert (
        client.post(
            "/api/auth/login",
            headers={"Content-Type": "application/json"},
            content=iter([b" " * 40000, b" " * 40000]),
        ).status_code
        == 413
    )


def test_concurrent_owner_demotion_keeps_an_owner(h: Harness) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from app.modules.identity.models import WorkspaceMembership

    owner_headers = h.login()
    member_headers = h.login("member")
    owner, member = h.clients["owner"], h.clients["member"]
    workspace, _, _, _ = flow(owner, owner_headers)
    path = f"/api/workspaces/{workspace}/members"
    assert (
        owner.put(
            path, headers=owner_headers, json={"email": h.emails["member"], "role": "owner"}
        ).status_code
        == 200
    )

    def demote(name: str) -> int:
        client, headers = (owner, owner_headers) if name == "owner" else (member, member_headers)
        return client.put(
            path, headers=headers, json={"email": h.emails[name], "role": "member"}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(demote, ["owner", "member"])) == [200, 409]
    with h.engine.connect() as database:
        owners = database.execute(
            select(WorkspaceMembership.user_id).where(
                WorkspaceMembership.workspace_id == workspace, WorkspaceMembership.role == "owner"
            )
        ).all()
        assert len(owners) == 1


def test_registration_cannot_fake_oauth_and_checks_timezone(h: Harness) -> None:
    headers = h.login()
    client = h.clients["owner"]
    workspace, _, brand, _ = flow(client, headers)
    path = f"/api/workspaces/{workspace}/brands/{brand}/accounts"
    data = {"platform": "youtube", "handle": "@different"}
    assert (
        client.post(
            path, headers=headers, json={**data, "connection_status": "CONNECTED"}
        ).status_code
        == 422
    )
    assert (
        client.post(path, headers=headers, json={**data, "timezone": "Not/A_Timezone"}).status_code
        == 422
    )
    assert (
        client.post(
            path, headers=headers, json={**data, "profile_url": "javascript:alert(1)"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, headers=headers, json={**data, "password": "not-accepted-platform-password"}
        ).status_code
        == 422
    )
