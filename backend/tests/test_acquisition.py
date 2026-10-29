import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from test_identity import Harness, flow
from test_identity import h as h
from test_media_storage import clip as clip

from app.modules.acquisition.models import MediaObject
from app.workers.acquisition_tasks import execute_job

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("CISRICE_INTEGRATION") != "1", reason="real services not enabled"),
]


def setup_media(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clip: Path
) -> tuple[str, dict[str, str], str]:
    headers = h.login()
    workspace, _, brand, _ = flow(h.clients["owner"], headers)
    root = f"/api/workspaces/{workspace}/brands/{brand}/media"
    settings = {
        "STORAGE_ROOT": str(tmp_path / "media"),
        "MINIMUM_FREE_BYTES": "0",
        "MAX_MEDIA_BYTES": "1048576",
        "STORAGE_QUOTA_BYTES": "10485760",
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
        setattr(h.settings, key.lower(), value if key == "STORAGE_ROOT" else int(value))

    def fixture_download(url, destination, limit, heartbeat, reserve):
        assert url == "https://example.org/owned.mp4"
        shutil.copyfile(clip, destination)
        heartbeat(75)

    monkeypatch.setattr("app.workers.acquisition_tasks.download", fixture_download)
    return root, headers, workspace


def approve(h: Harness, root: str, headers: dict[str, str], title: str = "Owned fixture") -> dict:
    response = h.clients["owner"].post(
        root + "/rights",
        headers=headers,
        json={
            "title": title,
            "source_url": "https://example.org/owned.mp4",
            "adapter": "direct",
            "basis": "OWNED",
            "license": "Owned test fixture",
            "evidence": "Generated locally for automated tests",
            "confirmed": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def request(
    h: Harness, root: str, headers: dict[str, str], rights: str, key: str | None = None
) -> dict:
    response = h.clients["owner"].post(
        root + "/requests",
        headers=headers,
        json={"rights_id": rights, "idempotency_key": key or str(uuid4())},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_authorized_acquisition_dedup_library_and_revocation(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clip: Path
) -> None:
    root, headers, _ = setup_media(h, tmp_path, monkeypatch, clip)
    client = h.clients["owner"]
    rights = approve(h, root, headers)
    key = str(uuid4())
    job = request(h, root, headers, rights["id"], key)
    assert request(h, root, headers, rights["id"], key)["id"] == job["id"]
    execute_job(job["id"])
    execute_job(job["id"])
    result = client.get(root + "/jobs").json()[0]
    assert result["state"] == "SUCCEEDED" and result["attempts"] == 1, result
    assets = client.get(root + "/assets").json()
    assert len(assets) == 1 and assets[0]["width"] == 160
    assert client.get(root + f"/assets/{assets[0]['id']}/file").content == clip.read_bytes()
    second_rights = approve(h, root, headers, "Second review")
    execute_job(request(h, root, headers, second_rights["id"])["id"])
    assets = client.get(root + "/assets").json()
    assert len(assets) == 2 and len({a["sha256"] for a in assets}) == 1
    assert len(list((tmp_path / "media" / "objects").rglob("*.mp4"))) == 1
    with Session(h.engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(MediaObject)
                .where(MediaObject.sha256 == assets[0]["sha256"])
            )
            == 1
        )
    with pytest.raises(ProgrammingError), Session(h.engine) as protected_db, protected_db.begin():
        protected_db.execute(
            update(MediaObject).where(MediaObject.sha256 == assets[0]["sha256"]).values(width=999)
        )
    client.post(root + f"/rights/{rights['id']}/revoke", headers=headers)
    original = next(a for a in assets if a["rights_id"] == rights["id"])
    assert client.get(root + f"/assets/{original['id']}/file").status_code == 409
    assert (
        client.post(
            root + "/requests",
            headers=headers,
            json={"rights_id": rights["id"], "idempotency_key": str(uuid4())},
        ).status_code
        == 409
    )
    assert len(list((tmp_path / "media" / "objects").rglob("*.mp4"))) == 1


def test_acquisition_unknown_rights_scope_and_cancel(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clip: Path
) -> None:
    root, headers, _ = setup_media(h, tmp_path, monkeypatch, clip)
    client = h.clients["owner"]
    assert (
        client.post(
            root + "/requests",
            headers=headers,
            json={"rights_id": str(uuid4()), "idempotency_key": str(uuid4())},
        ).status_code
        == 404
    )
    rights = approve(h, root, headers)
    job = request(h, root, headers, rights["id"])
    assert (
        client.post(root + f"/jobs/{job['id']}/cancel", headers=headers).json()["state"]
        == "CANCELLED"
    )
    execute_job(job["id"])
    assert client.get(root + "/assets").json() == []
    other_headers = h.login("other")
    other = h.clients["other"]
    assert other.get(root + "/rights").status_code == 404
    assert other.get(root + "/assets").status_code == 404
    assert other.post(root + f"/jobs/{job['id']}/cancel", headers=other_headers).status_code == 404


def test_running_cancel_and_revoked_rights_cannot_register(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clip: Path
) -> None:
    root, headers, _ = setup_media(h, tmp_path, monkeypatch, clip)
    client = h.clients["owner"]
    rights = approve(h, root, headers)
    job = request(h, root, headers, rights["id"])

    def cancelled(url, destination, limit, heartbeat, reserve):
        client.post(root + f"/jobs/{job['id']}/cancel", headers=headers)
        heartbeat(40)

    monkeypatch.setattr("app.workers.acquisition_tasks.download", cancelled)
    execute_job(job["id"])
    assert client.get(root + "/jobs").json()[0]["state"] == "CANCELLED"
    second = request(h, root, headers, rights["id"])

    def revoked(url, destination, limit, heartbeat, reserve):
        client.post(root + f"/rights/{rights['id']}/revoke", headers=headers)
        heartbeat(40)

    monkeypatch.setattr("app.workers.acquisition_tasks.download", revoked)
    execute_job(second["id"])
    assert client.get(root + "/assets").json() == []
    assert client.get(root + "/jobs").json()[0]["state"] == "FAILED"


def test_invalid_media_quarantine_and_disk_failure(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clip: Path
) -> None:
    root, headers, _ = setup_media(h, tmp_path, monkeypatch, clip)
    rights = approve(h, root, headers)

    def invalid(url, destination, limit, heartbeat, reserve):
        destination.write_bytes(b"invalid media")

    monkeypatch.setattr("app.workers.acquisition_tasks.download", invalid)
    job = request(h, root, headers, rights["id"])
    execute_job(job["id"])
    assert h.clients["owner"].get(root + "/jobs").json()[0]["state"] == "FAILED"
    assert (tmp_path / "media" / "quarantine" / job["id"]).exists()
    assert h.clients["owner"].get(root + "/assets").json() == []
    monkeypatch.setenv("MINIMUM_FREE_BYTES", str(2**60))
    second = request(h, root, headers, rights["id"])
    execute_job(second["id"])
    assert (
        h.clients["owner"].get(root + "/jobs").json()[0]["error_code"] == "insufficient_disk_space"
    )


def test_cross_brand_reuse_requires_destination_rights_and_access(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clip: Path
) -> None:
    root, headers, workspace = setup_media(h, tmp_path, monkeypatch, clip)
    client = h.clients["owner"]
    rights = approve(h, root, headers)
    execute_job(request(h, root, headers, rights["id"])["id"])
    asset = client.get(root + "/assets").json()[0]
    niche = client.get(f"/api/workspaces/{workspace}/niches").json()[0]["id"]
    target = client.post(
        f"/api/workspaces/{workspace}/brands",
        headers=headers,
        json={"name": "Reuse destination", "niche_id": niche},
    ).json()["id"]
    destination = f"/api/workspaces/{workspace}/brands/{target}/media"
    target_rights = approve(h, destination, headers, "Destination ownership")
    response = client.post(
        destination + "/reuse",
        headers=headers,
        json={
            "source_brand_id": root.split("/")[5],
            "source_asset_id": asset["id"],
            "destination_rights_id": target_rights["id"],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["sha256"] == asset["sha256"]
    assert len(list((tmp_path / "media" / "objects").rglob("*.mp4"))) == 1
    assert client.get(destination + f"/assets/{asset['id']}/file").status_code == 404
    assert (
        client.get(destination + f"/assets/{response.json()['id']}/file").content
        == clip.read_bytes()
    )
    member_headers = h.login("member")
    client.put(
        f"/api/workspaces/{workspace}/members",
        headers=headers,
        json={"email": h.emails["member"], "role": "member"},
    )
    client.put(
        f"/api/workspaces/{workspace}/brands/{target}/permissions",
        headers=headers,
        json={"email": h.emails["member"], "role": "editor"},
    )
    assert (
        h.clients["member"]
        .post(
            destination + "/reuse",
            headers=member_headers,
            json={
                "source_brand_id": root.split("/")[5],
                "source_asset_id": asset["id"],
                "destination_rights_id": target_rights["id"],
            },
        )
        .status_code
        == 404
    )


def test_originating_actor_revocation_stops_active_acquisition(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clip: Path
) -> None:
    root, headers, workspace = setup_media(h, tmp_path, monkeypatch, clip)
    client = h.clients["owner"]
    brand = root.split("/")[5]
    rights = approve(h, root, headers)
    client.put(
        f"/api/workspaces/{workspace}/members",
        headers=headers,
        json={"email": h.emails["member"], "role": "member"},
    )
    client.put(
        f"/api/workspaces/{workspace}/brands/{brand}/permissions",
        headers=headers,
        json={"email": h.emails["member"], "role": "editor"},
    )
    member_headers = h.login("member")
    response = h.clients["member"].post(
        root + "/requests",
        headers=member_headers,
        json={"rights_id": rights["id"], "idempotency_key": str(uuid4())},
    )
    assert response.status_code == 202

    def revoke(url, destination, limit, heartbeat, reserve):
        client.delete(
            f"/api/workspaces/{workspace}/brands/{brand}/permissions/{h.users['member'].id}",
            headers=headers,
        )
        heartbeat(40)

    monkeypatch.setattr("app.workers.acquisition_tasks.download", revoke)
    execute_job(response.json()["id"])
    assert client.get(root + "/assets").json() == []
    assert client.get(root + "/jobs").json()[0]["error_code"] == "permission_revoked"
