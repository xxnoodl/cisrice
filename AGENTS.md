# Repository conventions

Implement the earliest incomplete milestone. Never report unrun checks as passing.
Python uses Ruff, strict mypy, pytest, SQLAlchemy 2 typed mappings and Alembic.
Frontend uses strict TypeScript, ESLint, Prettier, Vitest and semantic HTML.
Routes call application services; repositories own database access. Domain modules
must not mutate each other's internal entities. Cross-module contracts belong in contracts/.

Security: enforce workspace/brand authorization server-side before adding user data.
Never put secrets in logs, commits, API responses or frontend configuration. No business
endpoints before authentication. Never publish without explicit authorization. Validate
URLs, storage paths and subprocess argument arrays before adding acquisition.
PostgreSQL will own durable job state; Redis is transport only. No business Celery tasks
until durable records, idempotency and cancellation have tests.

Checks (from repository root):
```
python -m ruff check backend
python -m ruff format --check backend
python -m mypy --config-file backend/pyproject.toml backend/app
python -m pytest backend/tests
cd frontend
npm run lint
npm run format:check
npm test
npm run build
```
With services: run Alembic upgrade, check, downgrade base, upgrade head against a
disposable database; set CISRICE_INTEGRATION=1 and run integration tests.
Definition of done: acceptance criteria satisfied, relevant checks passing, security
review complete, limitations and verification evidence recorded in STATUS.md.
Update README, plan, decisions and status for each milestone. No delegation required.
