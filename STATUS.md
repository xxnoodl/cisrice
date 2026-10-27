# Implementation status

Milestone 0: complete on native Linux (2026-10-27). Windows/WSL2 deployment remains
unverified. Milestone 1 has not started. This is a working health/dashboard foundation, not the full product.

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
- Native Linux container deployment and real PostgreSQL/Redis/worker checks are verified.
  Windows/WSL2 deployment remains unverified; no Windows container-runtime claim is made.
- CI defines these checks but has not been executed in this session.
- No OAuth, publishing, AI or other external product integrations implemented.

## Outstanding
- Existing GitHub MIT license preserved during history integration. Full resolved
  dependency/image license compatibility and distribution audit remains pending.
- Before M1 business APIs: least-privilege runtime DB role, authentication, rate limits,
  scoped authorization and audit. Credential encryption precedes token storage.
- No media data, backups, restore guarantees, resource coordination or offline cache yet.

Next milestone: M1 portfolio and identity; retain publishing approval and brand isolation requirements.

## Handoff preference
Continue development and deployment verification on native Linux. The user does not
want to install or run WSL on this Windows machine. Windows/WSL2 remains an unverified
optional deployment target; it is not a prerequisite for the Linux continuation.

## Linux verification checkpoint (2026-10-27)
- Work resumed on native Arch Linux through SSH; working tree was clean at 4268340.
- Host: Python 3.14.7, Node 26.10.0, npm 12.1.0; uv created an isolated Python
  3.12.13 environment to match the reference container/CI Python version.
- Backend Ruff lint/format and strict mypy pass. pytest: 4 passed, 1 real-service
  integration test skipped. pip check passes; pip-audit reports no known vulnerabilities
  (the unpublished local project itself is not audited through PyPI).
- Frontend npm ci reports zero vulnerabilities. ESLint, Prettier, all 4 Vitest tests,
  TypeScript checking and the production build pass on Linux.
- npm 12 blocked esbuild's postinstall script by default; the optional platform binary
  was available and both the tests and build succeeded without overriding that policy.
- Docker/Compose/buildx setup requires interactive sudo on this machine. Container
  startup, live PostgreSQL/Redis checks, worker ping, migration round trip and a
  container-served browser smoke remain unverified until that setup is complete.

## Milestone 0 deployment acceptance (2026-10-27)
- Docker 29.9.2 and Compose 5.6.1 verified on native Arch Linux after rebooting into
  kernel 7.2.11. Before reboot, the running 7.2.7 kernel had no matching installed
  modules, preventing Docker bridge networking. No firewall protections were disabled.
- `docker compose config --quiet` and `docker compose up --build --wait` passed.
  All application images built; the one-shot migration exited successfully.
- API and frontend-proxied readiness return HTTP 200 with PostgreSQL, Redis and
  migration revision checks all ok. Celery worker inspect ping returns pong.
- All 5 backend tests pass against actual PostgreSQL/Redis. Alembic upgrade/check,
  downgrade-to-base, re-upgrade/check and post-upgrade integration test pass.
  Only a uniquely named disposable test database was created and dropped. Application
  database and volumes were preserved. Reproduce with infrastructure/scripts/verify_linux.py.
- Container-served overview and operations routes rendered in installed Windows Edge
  through a temporary localhost SSH tunnel. This verifies Linux serving/browser
  rendering, not Windows/WSL2 container deployment. The temporary tunnel was closed.
- API and worker run as uid 10001; nginx runs as uid 101. Published host ports bind
  only 127.0.0.1; database/cache have no published host ports. Generated .env is mode
  0600 and ignored by Git; credentials were not logged or committed.
- Application stack remains running on Linux localhost:8080 (dashboard) and :8000
  (API). Docker service was started for this session; boot auto-start is not configured.
- Existing development quality gates and frontend's 4 tests passed on this Linux
  checkout. Upstream TestClient deprecation warning remains non-fatal. CI execution,
  full third-party distribution licensing audit and Windows deployment remain unverified.
