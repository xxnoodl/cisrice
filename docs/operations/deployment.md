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
CI defines this round trip. Actual native Linux Compose validation and the round
trip passed on 2026-10-27; remote CI execution remains unverified.
No verified backup procedure yet. Protect .env, retain volumes and export data before
upgrades. Future credential keys must live outside PostgreSQL with separate backups;
no tokens or encryption subsystem exist yet.

## Verified native Linux procedure

Arch Linux kernel 7.2.11, Docker 29.9.2 and Compose 5.6.1 were used for acceptance.
Run the stack with `docker compose up --build --wait --wait-timeout 180`, then use
`.venv/bin/python infrastructure/scripts/verify_linux.py` from the repository root.
The verifier requires backend[dev] installed, Docker group access, a private .env,
and the already-running postgres/redis/api/frontend/worker services. It uses host
access to Docker bridge addresses without publishing database or Redis ports.
A new UUID-named database is created, migrated, tested, downgraded, re-migrated and
removed in a finally block. If interrupted before cleanup, inspect databases with
the `cisrice_verify_` prefix and remove only confirmed leftover test databases;
never downgrade or drop the application database.

On Arch after a kernel update, reboot before starting Docker if installed modules
do not match `uname -r`. The observed missing overlay/addrtype module startup failure
was resolved by booting the installed kernel, without disabling firewall management.
Reference: https://wiki.archlinux.org/title/Kernel_module#Manual_module_handling.

For browser access from another machine, keep application ports bound to localhost
and use an SSH tunnel, for example `ssh -N -L 8080:127.0.0.1:8080 user@linux-host`.
Open http://localhost:8080 on the client. Browser rendering was verified through
this path; Windows/WSL2 Docker deployment itself is still unverified.
The application containers remain running after acceptance. Docker daemon and
application auto-start at boot are not configured by the startup script.
