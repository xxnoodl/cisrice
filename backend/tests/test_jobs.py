import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_identity import Harness, flow
from test_identity import h as h

from app.modules.operations.job_repository import JobCancelled, JobRepository, LeaseLost

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("CISRICE_INTEGRATION") != "1", reason="real services not enabled"),
]


def queued(h: Harness) -> tuple[UUID, UUID, UUID]:
    workspace, _, brand, _ = flow(h.clients["owner"], h.login())
    with Session(h.engine) as db, db.begin():
        row = JobRepository(db).enqueue(
            UUID(workspace),
            UUID(brand),
            h.users["owner"].id,
            "test.fixture",
            uuid4().hex,
            {"fixture": "one"},
            uuid4().hex,
        )
        return UUID(workspace), UUID(brand), row.id


def test_job_idempotency_delivery_and_completion(h: Harness) -> None:
    workspace, brand, job = queued(h)
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        row = repo.get(job)
        assert row
        assert (
            repo.enqueue(
                workspace,
                brand,
                row.actor_id,
                row.job_type,
                row.idempotency_key,
                row.payload,
                "second-correlation",
            ).id
            == job
        )
        with pytest.raises(ValueError):
            repo.enqueue(
                workspace,
                brand,
                row.actor_id,
                row.job_type,
                row.idempotency_key,
                {"fixture": "different"},
                "second",
            )
        claimed = repo.claim(job)
        assert claimed and claimed.attempts == 1 and claimed.lease_token
        token = claimed.lease_token
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        assert repo.claim(job) is None
        repo.heartbeat(job, token, 70)
        assert repo.get(job).progress == 70
        repo.finish(job, token)
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        assert repo.claim(job) is None
        assert repo.get(job).state == "SUCCEEDED"
        with pytest.raises(LeaseLost):
            repo.finish(job, token)


def test_job_cancellation_blocks_completion_and_scope(h: Harness) -> None:
    workspace, brand, job = queued(h)
    with Session(h.engine) as holder, holder.begin(), Session(h.engine) as scoped, scoped.begin():
        JobRepository(holder).get(job, lock=True)
        scoped.execute(text("SET LOCAL lock_timeout = '100ms'"))
        assert JobRepository(scoped).cancel(workspace, uuid4(), job) is None
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        assert repo.cancel(workspace, uuid4(), job) is None
        row = repo.claim(job)
        assert row and row.lease_token
        token = row.lease_token
        assert repo.cancel(workspace, brand, job).cancel_requested
        with pytest.raises(JobCancelled):
            repo.heartbeat(job, token, 80)
        with pytest.raises(JobCancelled):
            repo.finish(job, token)
        repo.fail(job, token, "cancelled", retryable=False)
        assert repo.get(job).state == "CANCELLED"
    _, _, second = queued(h)
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        row = repo.get(second)
        assert repo.cancel(row.workspace_id, row.brand_id, second).state == "CANCELLED"
        assert repo.claim(second) is None


def test_job_expired_worker_fencing_and_crash_retry_budget(h: Harness) -> None:
    _, _, job = queued(h)
    old = datetime.now(UTC) - timedelta(minutes=5)
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        row = repo.get(job)
        row.next_attempt_at = old
        row.next_dispatch_at = old
        repo.save(row)
        assert job in repo.dispatchable()
        assert job not in repo.dispatchable()
        row = repo.claim(job, now=old)
        token = row.lease_token
    with Session(h.engine) as db, db.begin():
        repo = JobRepository(db)
        row = repo.claim(job)
        assert row and row.attempts == 2 and row.lease_token != token
        current = row.lease_token
        with pytest.raises(LeaseLost):
            repo.finish(job, token)
        repo.fail(job, current, "network_unavailable", retryable=True)
        assert repo.get(job).state == "RETRY"
        assert repo.claim(job) is None
        row = repo.claim(job, now=datetime.now(UTC) + timedelta(minutes=1))
        assert row and row.attempts == 3
        assert row.progress == 0 and row.error_code == ""
        repo.fail(job, row.lease_token, "network_unavailable", retryable=True)
        assert repo.get(job).state == "FAILED"


def test_job_uncommitted_creation_rolls_back(h: Harness) -> None:
    workspace, brand, _ = queued(h)
    with Session(h.engine) as db:
        row = JobRepository(db).enqueue(
            workspace,
            brand,
            h.users["owner"].id,
            "test.fixture",
            uuid4().hex,
            {},
            "transaction-fixture",
        )
        identifier = row.id
        db.rollback()
    with Session(h.engine) as db:
        assert JobRepository(db).get(identifier) is None
