# Implementation status

Milestone 0: implemented, acceptance pending deployment verification. Milestone 1 has
not started. This is a working health/dashboard foundation, not the full product.

## Implemented
- Monorepo, modular backend structure, React dashboard with labeled planned areas.
- FastAPI liveness/readiness, real PostgreSQL/Redis adapters, revision check and
  correlation IDs; dependency error details redacted.
- SQLAlchemy foundation model and Alembic upgrade/downgrade.
- Celery worker configuration with no business tasks; no Redis-authoritative jobs.
- Compose with migration gating, localhost bindings, isolated database/cache ports,
  non-root application containers and persistent database/cache volumes.
- Tests, CI, ten ADRs, development/deployment/license documentation and wrappers.

## Verification checkpoint (2026-10-25)
- Host: Windows PowerShell; Git, Python 3.14.5, Node 24.16.0, npm 11.13.0,
  FFmpeg/ffprobe available. Docker, PostgreSQL and Redis absent. Full-path wsl.exe
  --status confirms Windows Subsystem for Linux is not installed.
- Backend: Ruff lint passed; strict mypy passed for 23 source files.
- pytest: 4 passed, 1 real-service test skipped. Offline Alembic SQL generation tested.
- Upstream Starlette warns that httpx-based TestClient is deprecated; tests pass.
- Python pip check passed. pip-audit passes after upgrading pip 26.1.1 to 26.2.2;
  local unpublished project is not auditable through PyPI. Installed dependency/license
  declarations recorded in docs/development/python-inventory.json.
- Real Uvicorn HTTP smoke: liveness 200; dependency-unavailable readiness 503.
- Linux shell wrapper syntax checked with Git Bash; PowerShell wrapper syntax checked
  with the PowerShell parser. This does not verify either deployment runtime.
- Frontend: ESLint 10 lint, Prettier format check, TypeScript check and Vite 7.3.7
  production build pass. Vitest 5.0.5: 4 tests pass. Final npm install audit reports
  zero vulnerabilities after resolving the initial test-tool advisories.
- Built dashboard rendered successfully in installed headless Microsoft Edge at both
  / and /operations, with health panel and navigation mounted. Browser smoke checks
  rendering only; it does not verify full-stack service connectivity or future workflows.
- This workspace sandbox denied esbuild ancestor-directory access; build, test and
  preview succeeded with approved execution outside the sandbox.

## Mocked / blocked
- Backend unit tests inject explicit dependency probes; no simulated platform data.
- Docker build/start, PostgreSQL migration execution/round trip, real Redis connectivity,
  Celery readiness, Linux and Windows/WSL2 deployment validation blocked by absent Docker.
- CI defines these checks but has not been executed in this session.
- No OAuth, publishing, AI or other external product integrations implemented.

## Outstanding
- Run documented Compose acceptance and migration round trip on disposable services.
- Existing GitHub MIT license preserved during history integration. Full resolved
  dependency/image license compatibility and distribution audit remains pending.
- Before M1 business APIs: least-privilege runtime DB role, authentication, rate limits,
  scoped authorization and audit. Credential encryption precedes token storage.
- No media data, backups, restore guarantees, resource coordination or offline cache yet.

Next milestone: finish M0 acceptance; only then begin M1 portfolio and identity.

## Handoff preference
Continue development and deployment verification on native Linux. The user does not
want to install or run WSL on this Windows machine. Windows/WSL2 remains an unverified
optional deployment target; it is not a prerequisite for the Linux continuation.
