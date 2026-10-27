# Implementation status

Milestones 0 and 1 are complete and verified on native Linux (2026-10-27).
Next milestone: 2, discovery. Windows container deployment and remote CI remain unverified.

## Implemented
- FastAPI/React foundation, PostgreSQL/Alembic, Redis/Celery infrastructure and health dashboard.
- Local operator-provisioned users, Argon2id passwords, opaque database-backed sessions,
  login rotation, expiry, logout, CSRF, trusted origins/hosts and Redis rate limits.
- Workspace memberships, niches, brands, style guides and platform account registration.
- Server-side workspace, brand and account permissions, last-owner protection,
  transactional audit records, and frontend context switching/settings.
- Revision 0002 and separate restricted runtime database role. Runtime cannot create
  schema objects or update/delete audit events. Operator credentials stay outside runtime.
- Accessible portfolio forms, membership and permission controls, audit display,
  and clear registered versus connected account states.
- Linux verification utility with disposable database and isolated browser credentials.

## Verified
- Native Arch Linux, Docker 29.9.2, Compose 5.6.1; isolated Python 3.12.13.
- Compose build/start passed; API and frontend readiness and Celery ping passed.
- Ruff lint/format and strict mypy passed; frontend ESLint, Prettier, TypeScript and build passed.
- 18 backend tests passed with real PostgreSQL/Redis and the restricted database role.
- 7 frontend component tests and 2 isolated Playwright tests passed.
- Additional Playwright smoke passed against the deployed localhost:8080 dashboard.
- Migration upgrade/check, downgrade to base, re-upgrade/check and post-upgrade
  service test passed. Only the disposable verification database was removed.
- Authorization tests cover cross-workspace/brand/account denial, revocation and
  concurrent owner demotion. Security tests cover CSRF, request limits, expiry,
  role restrictions, and safe logout during Redis outage.
- Application database/volumes preserved. No default user or password seeded.
- .env remains ignored and mode 0600. PostgreSQL/Redis have no published ports;
  application ports bind localhost. No external publishing occurred.
- Earlier dependency scans reported no known Python/npm vulnerabilities;
  this is not a complete third-party distribution/license audit.

## Mocked and external integrations
- Unit tests inject labeled dependency probes; no simulated platform analytics.
- PostgreSQL, Redis, migrations, Celery heartbeat and browser workflows use real services.
- No OAuth, platform publishing, discovery, acquisition or AI integration implemented yet.
- Platform accounts are registered only; registration does not claim connection.

## Limitations
- Operator CLI creates users; invitations, self-service password recovery and OAuth are deferred.
- UI lists are bounded; large-library pagination remains future work.
- Windows/WSL2 deployment, GitHub-hosted CI execution and backup/restore remain unverified.
- Existing GitHub MIT license retained; full resolved dependency/image compatibility review pending.
- Upstream Starlette TestClient deprecation warning is non-fatal.
- Docker boot auto-start has not been configured. Native Linux via SSH is the user's
  preferred workflow; WSL is not required.
- No business Celery tasks until durable jobs, idempotency and cancellation are implemented.

## Start and first user
From ~/cisrice run docker compose up --build --wait.
Create a user interactively with:
    docker compose exec api python -m app.modules.identity.cli create-user --email you@example.com
Open http://localhost:8080 on Linux, or forward that port over SSH from Windows.
