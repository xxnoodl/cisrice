import shutil
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import make_engine
from app.core.network import NetworkPolicyError
from app.integrations.acquisition_http import download
from app.integrations.ytdlp import inspect_media
from app.modules.acquisition.repository import AcquisitionRepository
from app.modules.acquisition.service import AcquisitionService
from app.modules.acquisition.storage import MediaError, MediaStorage, probe, validate_decode
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.service import IdentityService
from app.modules.operations.job_repository import JobCancelled, JobRepository, LeaseLost
from app.modules.operations.job_service import JobLifecycle
from app.workers.celery_app import celery_app


def execute_job(identifier: str) -> None:
    settings = Settings()
    engine = make_engine(settings)
    token = None
    stage: Path | None = None
    storage: MediaStorage | None = None
    try:
        job_id = UUID(identifier)
        # One acquisition/validation at a time across workers sharing this database.
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as resource:
            if not resource.scalar(text("SELECT pg_try_advisory_lock(1397314373, 1)")):
                return
            backend_pid = resource.scalar(text("SELECT pg_backend_pid()"))
            try:
                with Session(engine, expire_on_commit=False) as db, db.begin():
                    job = JobLifecycle(JobRepository(db)).claim(job_id)
                if job is None:
                    return
                token = job.lease_token
                if token is None:
                    return
                if job.job_type != "acquisition.download" or job.schema_version != 1:
                    raise MediaError("unsupported_job_type_or_version")
                rights_id = UUID(job.payload["rights_id"])

                def heartbeat(progress: int) -> None:
                    if resource.scalar(text("SELECT pg_backend_pid()")) != backend_pid:
                        raise MediaError("resource_lease_lost")
                    with Session(engine) as heartbeat_db, heartbeat_db.begin():
                        identity = IdentityService(
                            IdentityRepository(heartbeat_db), settings, job.correlation_id
                        )
                        identity.authorize_background(job.actor_id, job.workspace_id, job.brand_id)
                        rights = AcquisitionRepository(
                            heartbeat_db, job.workspace_id, job.brand_id
                        ).rights(rights_id)
                        if rights is None or rights.status != "APPROVED":
                            raise MediaError("rights_revoked")
                        JobLifecycle(JobRepository(heartbeat_db)).heartbeat(job_id, token, progress)

                with Session(engine) as db, db.begin():
                    identity = IdentityService(IdentityRepository(db), settings, job.correlation_id)
                    actor = identity.authorize_background(
                        job.actor_id, job.workspace_id, job.brand_id
                    )
                    service = AcquisitionService(
                        AcquisitionRepository(db, job.workspace_id, job.brand_id),
                        identity,
                        actor,
                        settings,
                    )
                    rights = service.rights(rights_id, approved=True)
                    url, adapter = rights.source_url, rights.adapter
                storage = MediaStorage(
                    settings.storage_root, settings.storage_quota_bytes, settings.minimum_free_bytes
                )
                storage.reserve(settings.max_media_bytes)
                stage = storage.staging(str(job_id), str(token))
                target = stage / "source.part"
                heartbeat(1)
                if adapter == "ytdlp":
                    url = inspect_media(url, heartbeat)
                download(url, target, settings.max_media_bytes, heartbeat, storage.reserve)
                heartbeat(85)
                try:
                    info = probe(target)
                    validate_decode(target, heartbeat)
                except MediaError:
                    storage.quarantine(target, str(job_id))
                    raise
                heartbeat(95)
                sha256, _ = storage.commit(target, info.extension, heartbeat)
                with Session(engine) as db, db.begin():
                    identity = IdentityService(IdentityRepository(db), settings, job.correlation_id)
                    actor = identity.authorize_background(
                        job.actor_id, job.workspace_id, job.brand_id
                    )
                    AcquisitionService(
                        AcquisitionRepository(db, job.workspace_id, job.brand_id),
                        identity,
                        actor,
                        settings,
                    ).complete(job_id, token, rights_id, sha256, target.stat().st_size, info)
            finally:
                try:
                    resource.execute(text("SELECT pg_advisory_unlock(1397314373, 1)"))
                except SQLAlchemyError:
                    pass
    except LeaseLost:
        pass
    except Exception as error:
        if token is not None:
            code = (
                "cancelled"
                if isinstance(error, JobCancelled)
                else "permission_revoked"
                if isinstance(error, HTTPException)
                else "unsafe_source"
                if isinstance(error, NetworkPolicyError)
                else str(error)
                if isinstance(error, MediaError)
                else "acquisition_failed"
            )
            retryable = code in {
                "network_unavailable",
                "partial_download",
                "resource_lease_lost",
                "source_http_429",
                "source_http_500",
                "source_http_502",
                "source_http_503",
                "source_http_504",
            }
            try:
                with Session(engine) as db, db.begin():
                    JobLifecycle(JobRepository(db)).fail(
                        UUID(identifier),
                        token,
                        code,
                        retryable,
                        retry_after=error.retry_after if isinstance(error, MediaError) else 0,
                    )
            except (SQLAlchemyError, LeaseLost):
                # Database/lease recovery is owned by the durable dispatcher.
                pass
    finally:
        if (
            stage is not None
            and storage is not None
            and stage.resolve().is_relative_to(storage.path("staging"))
        ):
            shutil.rmtree(stage)
        engine.dispose()


# Durable records, idempotency, cancellation and lease fencing passed tests before registration.
celery_app.task(
    name="cisrice.acquire",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=570,
    time_limit=600,
)(execute_job)
