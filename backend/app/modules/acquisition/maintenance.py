"""Operator-only retention. Canonical objects and database records are never deleted."""

import argparse
import shutil
from datetime import UTC, datetime, timedelta
from itertools import islice
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import make_engine
from app.modules.acquisition.storage import MediaStorage
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.service import IdentityService
from app.modules.operations.job_repository import TERMINAL, JobRepository


def expired_temporaries(
    storage: MediaStorage, settings: Settings, jobs: JobRepository
) -> list[tuple[Path, UUID, str]]:
    result: list[tuple[Path, UUID, str]] = []
    for folder, hours, pattern in [
        ("staging", settings.staging_retention_hours, "*/*"),
        ("quarantine", settings.quarantine_retention_days * 24, "*"),
    ]:
        if not hours:
            continue
        boundary = datetime.now(UTC) - timedelta(hours=hours)
        for item in islice(storage.path(folder).glob(pattern), 200):
            if item.is_symlink() or not item.resolve().is_relative_to(storage.path(folder)):
                continue
            try:
                identifier = UUID(item.parent.name if folder == "staging" else item.name)
                if folder == "staging":
                    UUID(item.name)
            except ValueError:
                continue
            job = jobs.get(identifier)
            if (
                job
                and job.state in TERMINAL
                and job.updated_at < boundary
                and item.stat().st_mtime < boundary.timestamp()
            ):
                result.append((item, identifier, folder))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect/purge expired temporary files; never deletes canonical media"
    )
    parser.add_argument("command", choices=["cleanup"])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually purge eligible temporary files (default is dry run)",
    )
    args = parser.parse_args()
    settings = Settings()
    storage = MediaStorage(
        settings.storage_root, settings.storage_quota_bytes, settings.minimum_free_bytes
    )
    engine = make_engine(settings)
    removed = 0
    try:
        with Session(engine) as db:
            candidates = expired_temporaries(storage, settings, JobRepository(db))
        if args.apply:
            for path, identifier, folder in candidates:
                with Session(engine) as db, db.begin():
                    repo = JobRepository(db)
                    job = repo.get(identifier, lock=True)
                    if job is None or job.state not in TERMINAL:
                        continue
                    workspace, brand = job.workspace_id, job.brand_id
                    IdentityService(IdentityRepository(db), settings, "operator-retention").record(
                        None, "storage.purge_intent", identifier, workspace, brand, {"kind": folder}
                    )
                # Verify the final absolute target before a recursive removal.
                final = path.resolve()
                if (
                    final == storage.path(folder)
                    or not final.is_relative_to(storage.path(folder))
                    or path.is_symlink()
                ):
                    continue
                if final.is_dir():
                    shutil.rmtree(final)
                else:
                    final.unlink()
                removed += 1
                with Session(engine) as db, db.begin():
                    IdentityService(IdentityRepository(db), settings, "operator-retention").record(
                        None,
                        "storage.temporary_purged",
                        identifier,
                        workspace,
                        brand,
                        {"kind": folder},
                    )
        print(f"Eligible: {len(candidates)}; purged: {removed}; canonical objects untouched")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
