import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from test_identity import Harness
from test_identity import h as h
from test_jobs import queued

from app.core.config import Settings
from app.modules.acquisition.maintenance import expired_temporaries
from app.modules.acquisition.storage import MediaStorage
from app.modules.operations.job_repository import JobRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("CISRICE_INTEGRATION") != "1", reason="real services not enabled"),
]


def test_retention_preserves_active_jobs_unknown_files_and_all_canonical_media(
    h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, terminal = queued(h)
    _, _, active = queued(h)
    storage = MediaStorage(str(tmp_path / "storage"), 1024**3, 0)
    settings = Settings(staging_retention_hours=24, quarantine_retention_days=1)
    old = datetime.now(UTC) - timedelta(days=3)
    eligible = storage.staging(str(terminal), str(uuid4()))
    protected = storage.staging(str(active), str(uuid4()))
    quarantine = storage.path("quarantine/" + str(terminal))
    quarantine.parent.mkdir(parents=True)
    quarantine.write_bytes(b"invalid fixture")
    canonical = storage.canonical("a" * 64, "mp4")
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(b"retained")
    for path in [eligible, protected, quarantine, canonical]:
        os.utime(path, (old.timestamp(), old.timestamp()))
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        row = repo.get(terminal)
        row.state = "FAILED"
        row.updated_at = old
        repo.save(row)
        paths = {entry[0] for entry in expired_temporaries(storage, settings, repo)}
        assert paths == {eligible, quarantine}
        assert protected.exists() and canonical.exists()
        # Inspection is a dry run, and zero disables quarantine retention.
        assert eligible.exists() and quarantine.exists()
        settings.quarantine_retention_days = 0
        assert {entry[0] for entry in expired_temporaries(storage, settings, repo)} == {eligible}

    from app.modules.acquisition.maintenance import main

    monkeypatch.setenv("STORAGE_ROOT", str(storage.root))
    monkeypatch.setenv("STAGING_RETENTION_HOURS", "24")
    monkeypatch.setenv("QUARANTINE_RETENTION_DAYS", "1")
    monkeypatch.setattr("sys.argv", ["retention", "cleanup"])
    main()
    assert eligible.exists() and quarantine.exists()
    monkeypatch.setattr("sys.argv", ["retention", "cleanup", "--apply"])
    main()
    assert not eligible.exists() and not quarantine.exists()
    assert protected.exists() and canonical.read_bytes() == b"retained"
