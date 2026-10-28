# Implementation status

Milestones 0–2 are complete and verified on native Linux (2026-10-28).
Next milestone: 3, rights-aware acquisition. Windows container deployment and remote CI remain unverified.

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
- No OAuth, platform publishing, acquisition or AI integration implemented yet.
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

## Milestone 2 acceptance (2026-10-28)
- Implemented brand-owned RSS/Atom and YouTube topic sources, policy acknowledgement,
  source pause/resume, synchronous bounded discovery, run history and source observations.
- Candidate inbox supports URL deduplication, possible duplicate-title indicators,
  publisher-topic/title/status filters, sorting/pagination, private notes and review.
- Configurable seven-signal weights preserve missing engagement/share/save data.
  Scores are initial editorial heuristics, not performance predictions; null when
  configured weights exclude all available signals. Rights always remain UNKNOWN.
- Explicit cross-brand copy checks edit permissions to both scopes, deduplicates,
  retains provenance, resets review state, excludes private notes and pauses copied sources.
- Added migration 0003. PostgreSQL role, authorization, DNS pinning/TLS verification,
  private-network/transition-address rejection, request/body limits and XML safety verified.
- Ruff lint/format, strict mypy, ESLint, Prettier, TypeScript/build pass.
- 25 backend tests pass with real PostgreSQL/Redis; 7 frontend component tests pass;
  2 isolated browser tests pass, including Discovery review/copy and portfolio isolation.
- Disposable migration upgrade/check/downgrade/re-upgrade/check and post-upgrade
  service test passed. No application data or volumes were removed.
- Deployment build/start, live readiness on 8000/8080, worker ping and deployed public
  browser smoke passed. Existing portfolio remains in the application database.
- Actual RSS HTTPS fetch/parser verified (35 items); no data imported into real brands.
  Documented YouTube endpoint returned valid empty Atom. Nonempty YouTube acquisition
  of metadata was verified only with fixtures; external availability is not guaranteed.
- Browser feed injection exists only in the test entrypoint. Production uses real HTTPS.
- pip check passes; pip-audit reports no known dependency vulnerabilities (local unpublished
  project skipped). No new frontend dependency introduced.
- Deferred: scheduled/asynchronous/autonomous discovery, Reddit and authorized API
  adapters, semantic topic clustering, source editing/deletion and historical rescoring.
  Feed categories provide topic filtering. Sources consolidate per-brand subscriptions;
  candidate notes consolidate initial research findings. Limits: 200 sources/brand,
  200 entries and 2 MiB/run, HTTPS only, no redirects/compression, 60-second cooldown.
  DNS resolution uses OS timeout; process crash rolls back an in-flight synchronous run.
- Windows deployment, remote CI execution, full licensing compatibility review and
  verified backup restoration remain outstanding. No business worker task introduced.
