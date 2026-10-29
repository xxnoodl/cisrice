from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.operations.job_models import DurableJob

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}


class LeaseLost(Exception):
    pass


class JobCancelled(Exception):
    pass


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, row: DurableJob) -> DurableJob:
        self.db.add(row)
        self.db.flush()
        return row

    def get(self, job: UUID, lock: bool = False) -> DurableJob | None:
        query = (
            select(DurableJob).where(DurableJob.id == job).execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def scoped(self, workspace: UUID, brand: UUID, job: UUID) -> DurableJob | None:
        return self.db.scalar(
            select(DurableJob).where(
                DurableJob.workspace_id == workspace,
                DurableJob.brand_id == brand,
                DurableJob.id == job,
            )
        )

    def list_jobs(self, workspace: UUID, brand: UUID, offset: int) -> list[DurableJob]:
        return list(
            self.db.scalars(
                select(DurableJob)
                .where(DurableJob.workspace_id == workspace, DurableJob.brand_id == brand)
                .order_by(DurableJob.created_at.desc(), DurableJob.id)
                .offset(offset)
                .limit(50)
            )
        )

    def enqueue(
        self,
        workspace: UUID,
        brand: UUID,
        actor: UUID,
        kind: str,
        key: str,
        payload: dict[str, str],
        correlation: str,
    ) -> DurableJob:
        # Serialize creation by brand, including an absent idempotency-key row.
        from sqlalchemy import text

        self.db.execute(text("SET LOCAL lock_timeout = '3s'"))
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": int.from_bytes(brand.bytes[:8], "big", signed=True)},
        )
        found = self.db.scalar(
            select(DurableJob).where(
                DurableJob.brand_id == brand,
                DurableJob.job_type == kind,
                DurableJob.idempotency_key == key,
            )
        )
        if found:
            if (
                found.workspace_id != workspace
                or found.actor_id != actor
                or found.payload != payload
            ):
                raise ValueError("Idempotency key already used for a different request")
            return found
        return self.save(
            DurableJob(
                workspace_id=workspace,
                brand_id=brand,
                actor_id=actor,
                job_type=kind,
                idempotency_key=key,
                payload=payload,
                correlation_id=correlation,
            )
        )

    def claim(self, job: UUID, now: datetime | None = None) -> DurableJob | None:
        now = now or datetime.now(UTC)
        row = self.get(job, lock=True)
        if row is None or row.state in TERMINAL:
            return None
        if row.state == "RUNNING" and row.lease_expires_at and row.lease_expires_at > now:
            return None
        if row.cancel_requested:
            row.state, row.lease_token, row.lease_expires_at = "CANCELLED", None, None
            self.save(row)
            return None
        if row.next_attempt_at > now:
            return None
        if row.attempts >= row.max_attempts:
            row.state, row.error_code = "FAILED", "attempt_budget_exhausted"
            row.lease_token, row.lease_expires_at = None, None
            self.save(row)
            return None
        row.state, row.lease_token = "RUNNING", uuid4()
        row.progress, row.error_code = 0, ""
        row.lease_expires_at = now + timedelta(seconds=45)
        row.attempts += 1
        row.updated_at = now
        return self.save(row)

    def require_lease(self, job: UUID, token: UUID) -> DurableJob:
        row = self.get(job, lock=True)
        now = datetime.now(UTC)
        if (
            row is None
            or row.state != "RUNNING"
            or row.lease_token != token
            or row.lease_expires_at is None
            or row.lease_expires_at <= now
        ):
            raise LeaseLost
        if row.cancel_requested:
            raise JobCancelled
        return row

    def heartbeat(self, job: UUID, token: UUID, progress: int) -> None:
        row = self.require_lease(job, token)
        row.progress = max(row.progress, min(99, max(0, progress)))
        row.updated_at = datetime.now(UTC)
        row.lease_expires_at = row.updated_at + timedelta(seconds=45)
        self.save(row)

    def finish(self, job: UUID, token: UUID) -> None:
        row = self.require_lease(job, token)
        row.state, row.progress = "SUCCEEDED", 100
        row.lease_token, row.lease_expires_at = None, None
        row.updated_at = datetime.now(UTC)
        self.save(row)

    def fail(
        self, job: UUID, token: UUID, code: str, retryable: bool, retry_after: int = 0
    ) -> None:
        row = self.get(job, lock=True)
        if (
            row is None
            or row.state != "RUNNING"
            or row.lease_token != token
            or row.lease_expires_at is None
            or row.lease_expires_at <= datetime.now(UTC)
        ):
            raise LeaseLost
        row.error_code = code
        row.state = (
            "CANCELLED"
            if row.cancel_requested
            else "RETRY"
            if retryable and row.attempts < row.max_attempts
            else "FAILED"
        )
        row.lease_token, row.lease_expires_at = None, None
        row.updated_at = datetime.now(UTC)
        row.next_attempt_at = row.updated_at + timedelta(
            seconds=max(15 * 2 ** max(0, row.attempts - 1), min(86400, max(0, retry_after)))
        )
        row.next_dispatch_at = row.next_attempt_at
        self.save(row)

    def cancel(self, workspace: UUID, brand: UUID, job: UUID) -> DurableJob | None:
        row = self.db.scalar(
            select(DurableJob)
            .where(
                DurableJob.id == job,
                DurableJob.workspace_id == workspace,
                DurableJob.brand_id == brand,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or row.workspace_id != workspace or row.brand_id != brand:
            return None
        if row.state in TERMINAL:
            return row
        row.cancel_requested = True
        if row.state != "RUNNING":
            row.state = "CANCELLED"
        row.updated_at = datetime.now(UTC)
        return self.save(row)

    def dispatchable(self) -> list[UUID]:
        now = datetime.now(UTC)
        rows = list(
            self.db.scalars(
                select(DurableJob)
                .where(
                    DurableJob.state.not_in(TERMINAL),
                    DurableJob.next_attempt_at <= now,
                    DurableJob.next_dispatch_at <= now,
                    or_(DurableJob.state != "RUNNING", DurableJob.lease_expires_at <= now),
                )
                .order_by(DurableJob.created_at)
                .with_for_update(skip_locked=True)
                .limit(20)
            )
        )
        for row in rows:
            row.next_dispatch_at = now + timedelta(seconds=30)
            self.save(row)
        return [row.id for row in rows]
