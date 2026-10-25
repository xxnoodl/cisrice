# Cisrice

Local-first, multi-brand social media research, media, production, publishing and
analytics platform. This repository currently implements the Milestone 0 foundation.
Authentication and all content workflows are planned, not available.

React/TypeScript/Vite dashboard → same-origin FastAPI modular monolith → PostgreSQL.
Celery uses Redis for transport; no business tasks are registered yet. Linux is the
reference target; Windows requires Docker Desktop using Linux containers and WSL2.
Both deployment paths remain unverified on the current machine because Docker is absent.

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
Docker startup, real database/Redis integration and Windows/WSL2 compatibility must be
verified before Milestone 0 acceptance. No backup/restore claims. License pending.
See STATUS.md for current evidence and IMPLEMENTATION_PLAN.md for remaining work.
