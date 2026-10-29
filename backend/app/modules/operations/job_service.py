from types import MappingProxyType
from uuid import UUID

from fastapi import HTTPException

from app.contracts.jobs import JobLease
from app.modules.identity.models import User
from app.modules.identity.service import IdentityService
from app.modules.operations.job_models import DurableJob
from app.modules.operations.job_repository import JobRepository


class JobService:
    def __init__(
        self,
        repo: JobRepository,
        identity: IdentityService,
        actor: User,
        workspace: UUID,
        brand: UUID,
    ) -> None:
        self.repo, self.identity, self.actor, self.workspace, self.brand = (
            repo,
            identity,
            actor,
            workspace,
            brand,
        )

    def list_jobs(self, offset: int) -> list[DurableJob]:
        self.identity.require_brand(self.actor, self.workspace, self.brand)
        return self.repo.list_jobs(self.workspace, self.brand, offset)

    def enqueue(self, kind: str, key: str, payload: dict[str, str]) -> DurableJob:
        self.identity.require_brand(self.actor, self.workspace, self.brand, write=True)
        try:
            row = self.repo.enqueue(
                self.workspace,
                self.brand,
                self.actor.id,
                kind,
                key,
                payload,
                self.identity.correlation,
            )
        except ValueError:
            raise HTTPException(
                409, "Idempotency key is already used for another request"
            ) from None
        self.identity.record(self.actor, "job.requested", row.id, self.workspace, self.brand)
        return row

    def cancel(self, identifier: UUID) -> DurableJob:
        self.identity.require_brand(self.actor, self.workspace, self.brand, write=True)
        row = self.repo.cancel(self.workspace, self.brand, identifier)
        if row is None:
            raise HTTPException(404, "Job not found")
        self.identity.record(
            self.actor, "job.cancellation_requested", row.id, self.workspace, self.brand
        )
        return row


class JobLifecycle:
    """Public worker contract; job entities never leave operations as mutable state."""

    def __init__(self, repo: JobRepository) -> None:
        self.repo = repo

    def claim(self, identifier: UUID) -> JobLease | None:
        row = self.repo.claim(identifier)
        if row is None or row.lease_token is None:
            return None
        return JobLease(
            row.id,
            row.workspace_id,
            row.brand_id,
            row.actor_id,
            row.job_type,
            row.schema_version,
            row.correlation_id,
            MappingProxyType(dict(row.payload)),
            row.lease_token,
        )

    def require_lease(self, identifier: UUID, token: UUID) -> None:
        self.repo.require_lease(identifier, token)

    def heartbeat(self, identifier: UUID, token: UUID, progress: int) -> None:
        self.repo.heartbeat(identifier, token, progress)

    def finish(self, identifier: UUID, token: UUID) -> None:
        self.repo.finish(identifier, token)

    def fail(
        self, identifier: UUID, token: UUID, code: str, retryable: bool, retry_after: int = 0
    ) -> None:
        self.repo.fail(identifier, token, code, retryable, retry_after=retry_after)

    def dispatchable(self) -> list[UUID]:
        return self.repo.dispatchable()
