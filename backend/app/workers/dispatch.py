"""PostgreSQL-backed dispatch outbox; repeated Redis deliveries are intentional."""

import time

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import make_engine
from app.modules.operations.job_repository import JobRepository
from app.modules.operations.job_service import JobLifecycle
from app.workers.celery_app import celery_app


def main() -> None:
    engine = make_engine(Settings())
    try:
        while True:
            try:
                with Session(engine) as db, db.begin():
                    identifiers = JobLifecycle(JobRepository(db)).dispatchable()
                for identifier in identifiers:
                    try:
                        celery_app.send_task("cisrice.acquire", args=[str(identifier)], retry=False)
                    except Exception:
                        # Do not log broker URLs or exceptions. DB schedules another delivery.
                        print(
                            "Dispatch temporarily unavailable; durable requests retained",
                            flush=True,
                        )
                        break
            except SQLAlchemyError:
                print("Job database temporarily unavailable; waiting to reconnect", flush=True)
            time.sleep(3)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
