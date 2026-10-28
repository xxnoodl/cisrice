import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session
from test_discovery import RSS
from test_identity import Harness, flow
from test_identity import h as h

from app.modules.discovery.feeds import FeedError
from app.modules.discovery.models import Source

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("CISRICE_INTEGRATION") != "1", reason="real services not enabled"),
]


def test_discovery_dedup_review_route_and_scope(h: Harness) -> None:
    headers = h.login()
    client = h.clients["owner"]
    workspace, niche, brand, _ = flow(client, headers)
    root = f"/api/workspaces/{workspace}/brands/{brand}/discovery"
    client.app.state.fetch_feed = lambda _: RSS
    source = client.post(
        root + "/sources",
        headers=headers,
        json={
            "name": "Fixture",
            "kind": "rss",
            "address": "https://example.org/feed",
            "keywords": ["technology"],
            "policy_note": "Authorized fixture",
            "policy_confirmed": True,
        },
    )
    assert source.status_code == 201, source.text
    source_id = source.json()["id"]
    assert client.post(root + f"/sources/{source_id}/runs").status_code == 403
    run = client.post(root + f"/sources/{source_id}/runs", headers=headers)
    assert run.status_code == 201 and run.json()["added"] == 2, run.text
    assert client.post(root + f"/sources/{source_id}/runs", headers=headers).status_code == 429
    with Session(h.engine) as db, db.begin():
        db.execute(
            update(Source)
            .where(Source.id == source_id)
            .values(last_run_at=datetime.now(UTC) - timedelta(minutes=2))
        )
    rerun = client.post(root + f"/sources/{source_id}/runs", headers=headers)
    assert rerun.json()["added"] == 0 and rerun.json()["duplicates"] == 2
    candidates = client.get(root + "/candidates").json()
    assert len(candidates) == 2
    assert all(c["duplicate_title"] and c["rights_status"] == "UNKNOWN" for c in candidates)
    assert candidates[0]["components"]["shares"] is None
    assert len(candidates[0]["observations"]) == 1
    assert len(client.get(root + "/candidates?topic=Technology").json()) == 1
    candidate = candidates[0]["id"]
    review = client.patch(
        root + f"/candidates/{candidate}",
        headers=headers,
        json={"status": "APPROVED", "notes": "Private notes"},
    )
    assert review.status_code == 200 and review.json()["rights_status"] == "UNKNOWN"
    assert len(client.get(root + "/candidates?status=APPROVED").json()) == 1
    target = client.post(
        f"/api/workspaces/{workspace}/brands",
        headers=headers,
        json={"name": "Target", "niche_id": niche},
    ).json()["id"]
    routed = client.post(
        root + f"/candidates/{candidate}/route", headers=headers, json={"target_brand_id": target}
    )
    assert routed.status_code == 200, routed.text
    assert routed.json()["notes"] == "" and routed.json()["status"] == "INBOX"
    destination = root.replace(brand, target)
    assert client.get(destination + "/sources").json()[0]["enabled"] is False
    assert (
        client.post(
            root + f"/candidates/{candidate}/route",
            headers=headers,
            json={"target_brand_id": target},
        ).status_code
        == 200
    )
    assert len(client.get(destination + "/candidates").json()) == 1
    other_headers = h.login("other")
    other = h.clients["other"]
    for path in ["/sources", "/candidates", "/runs"]:
        assert other.get(root + path).status_code == 404
    assert other.post(root + f"/sources/{source_id}/runs", headers=other_headers).status_code == 404
    assert (
        client.post(
            root + f"/candidates/{candidate}/route",
            headers=headers,
            json={"target_brand_id": str(uuid4())},
        ).status_code
        == 404
    )


def test_discovery_failure_history_and_viewer_denial(h: Harness) -> None:
    headers = h.login()
    client = h.clients["owner"]
    workspace, _, brand, _ = flow(client, headers)
    root = f"/api/workspaces/{workspace}/brands/{brand}/discovery"
    source = client.post(
        root + "/sources",
        headers=headers,
        json={
            "name": "Blocked fixture",
            "kind": "rss",
            "address": "https://example.org/feed",
            "policy_note": "Fixture permission",
            "policy_confirmed": True,
        },
    ).json()

    def fail(_: str) -> bytes:
        raise FeedError("Feed connection failed; check connectivity and retry later")

    client.app.state.fetch_feed = fail
    response = client.post(root + f"/sources/{source['id']}/runs", headers=headers)
    assert response.status_code == 201 and response.json()["state"] == "FAILED"
    assert client.get(root + "/runs").json()[0]["state"] == "FAILED"
    member_headers = h.login("member")
    client.put(
        f"/api/workspaces/{workspace}/members",
        headers=headers,
        json={"email": h.emails["member"], "role": "member"},
    )
    client.put(
        f"/api/workspaces/{workspace}/brands/{brand}/permissions",
        headers=headers,
        json={"email": h.emails["member"], "role": "viewer"},
    )
    member = h.clients["member"]
    assert member.get(root + "/sources").status_code == 200
    assert (
        member.post(root + f"/sources/{source['id']}/runs", headers=member_headers).status_code
        == 403
    )
