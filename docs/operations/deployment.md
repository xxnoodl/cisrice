# Deployment verification and recovery

Reference deployment uses Linux containers; native Windows Celery is unsupported.
Keep repository and Docker data inside WSL2 Linux storage for better filesystem I/O.
Do not expose the localhost ports publicly: this bootstrap has no authentication.
PostgreSQL/Redis have no published host ports. Application services use unprivileged users.
The database bootstrap user owns schema migrations; least-privilege runtime roles are
a prerequisite for authenticated business functionality.

After README startup, inspect `docker compose logs migrate api worker frontend`.
Readiness must be HTTP 200, dashboard must show all three checks ok, and worker logs
must show a ready worker. No application task execution is claimed in M0.
Run backend real-service tests against a disposable PostgreSQL 17 and Redis 7 instance:
set DATABASE_URL, REDIS_URL and CISRICE_INTEGRATION=1, then from backend:
```
alembic upgrade head
alembic check
python -m pytest
alembic downgrade base
alembic upgrade head
```
Downgrade destroys foundation metadata: use only a disposable test database.
CI exercises this round trip. Actual local Compose validation is still outstanding.
No verified backup procedure yet. Protect .env, retain volumes and export data before
upgrades. Future credential keys must live outside PostgreSQL with separate backups;
no tokens or encryption subsystem exist yet.
