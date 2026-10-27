# Cisrice

Local-first, multi-brand social media research, media, production, publishing and
analytics platform. Milestone 0 is implemented and verified on native Linux.
Authentication and all content workflows are planned, not available.

React/TypeScript/Vite dashboard → same-origin FastAPI modular monolith → PostgreSQL.
Celery uses Redis for transport; no business tasks are registered yet. Linux is the
reference target; Windows requires Docker Desktop using Linux containers and WSL2.
Backend/frontend development quality gates have passed on native Arch Linux.
Full container deployment is verified on native Linux. Windows/WSL2 compatibility
remains unverified; see STATUS.md for the exact verification checkpoint.

## Start

Prerequisites: Git, Docker Engine with Compose v2 on Linux, or Docker Desktop/WSL2 on
Windows. Allow network access for initial image/package downloads. No paid AI services.

Linux:
```sh
cp .env.example .env
# Edit .env: change POSTGRES_PASSWORD and matching DATABASE_URL password.
docker compose config --quiet
docker compose up --build -d
docker compose ps
curl --fail http://localhost:8000/api/health/ready
```

PowerShell:
```powershell
Copy-Item .env.example .env
# Edit .env: change POSTGRES_PASSWORD and matching DATABASE_URL password.
docker compose config --quiet
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/api/health/ready
```

Dashboard: http://localhost:8080. API docs: http://localhost:8000/docs.
Stop with `docker compose down` (preserves named database/Redis volumes).
Never use `down -v` against data you want to keep. This is not a verified backup system.

## Development

Python 3.12–3.14 and Node 24. From root:
```sh
python -m venv .venv
# Linux: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e './backend[dev]'
cd frontend
npm ci
npm run dev
```
In another activated terminal: `cd backend`, then
`uvicorn app.main:app --host 127.0.0.1 --port 8000`.
Vite proxies /api to localhost:8000. Without services, dashboard reports degraded.
For local services set DATABASE_URL and REDIS_URL explicitly; the root Compose .env
uses container hostnames and is not a host-development configuration.
Run `alembic upgrade head` from backend before readiness can pass.
See AGENTS.md for quality commands and docs/operations/deployment.md for verification.

## Limits

No authentication, discovery, media processing, inference, publishing or analytics yet.
No accounts connected; no mocked platform metrics. Only health endpoints are exposed.
Docker startup, PostgreSQL/Redis integration, worker ping and migration round trip
are verified on native Linux. Windows/WSL2 deployment remains unverified. No
backup/restore claims. The repository uses
the MIT license retained from its existing GitHub initial commit; third-party
distribution compatibility review remains pending.
See STATUS.md for current evidence and IMPLEMENTATION_PLAN.md for remaining work.

## Native Linux deployment verification

After starting Compose and installing backend development dependencies, run from root:

```sh
.venv/bin/python infrastructure/scripts/verify_linux.py
```
This checks both readiness endpoints and worker ping, then creates a uniquely named
disposable database for real-service tests and an Alembic migration round trip. It
drops only that temporary database, leaving application data and volumes intact.
The verifier uses Linux Docker bridge addresses and is not a Docker Desktop verifier.
See docs/operations/deployment.md for prerequisites and the verified environment.
