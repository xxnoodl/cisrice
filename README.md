# Cisrice

Cisrice is a local-first, multi-brand social media research, media, production,
publishing and analytics platform. Milestone 0 is verified on native Linux.
Milestones 1–2 implement local identity, portfolio management and bounded feed discovery; see STATUS.md for
the current verification checkpoint. Acquisition, production, publishing and analytics remain later milestones.

## Available functionality

- Local users, password-based sign-in, expiring sessions and logout.
- Workspace → niche → brand → registered platform-account hierarchy.
- Brand identity/style preferences, context switching and audit history.
- Workspace membership and explicit brand/account permissions with revocation.
- PostgreSQL-backed authorization and sessions; Redis-backed rate limits.
- Service health, Docker deployment and isolated database/browser verification.

Account registration does not connect OAuth or publish anything. Provider passwords
and tokens are not accepted. No synthetic analytics or successful connections are shown.

## Architecture and platforms

React/TypeScript/Vite → same-origin nginx proxy → FastAPI modular monolith →
PostgreSQL. Celery/Redis provide worker transport; no business tasks are registered
until durable PostgreSQL jobs and idempotent handlers are implemented.

Native Linux is the reference deployment. Windows can act as an SSH client to Linux
without WSL; that workflow is verified. Local Windows Docker Desktop/WSL2 deployment
remains unverified. macOS is not an initial acceptance target.

## Start on Linux

Requires Git, Docker Engine and Compose v2 or newer. Initial builds need network
access. No paid AI API or model download is required for current functionality.

From the cloned repository:

    cp .env.example .env
    chmod 600 .env

Edit .env with two distinct passwords: POSTGRES_PASSWORD for the operator/migrations
and APP_DATABASE_PASSWORD (at least 24 characters) for cisrice_app. Update the matching
MIGRATION_DATABASE_URL and DATABASE_URL password values.

    docker compose config --quiet
    docker compose up --build --wait --wait-timeout 180
    docker compose ps
    curl --fail http://localhost:8000/api/health/ready

Create your first user interactively; the password is prompted, never a command argument:

    docker compose exec api python -m app.modules.identity.cli create-user --email you@example.com

Open http://localhost:8080 and sign in. API docs: http://localhost:8000/docs.
Create a workspace, niche, brand and registered platform account through Portfolio.
Brand settings are also available through Settings, preserving selected context.
Additional users are created with the same operator command and granted access in
Portfolio. No default user or password is created.

Stop with docker compose down; named volumes are preserved. Do not use down -v for
data you want to retain. A verified migration round trip is not a backup/restore test.

For access from Windows, keep ports local and open an SSH tunnel:

    ssh -N -L 8080:127.0.0.1:8080 user@linux-host

Then visit http://localhost:8080 on Windows. Configure the appropriate SSH identity
if needed. Do not publish the API, PostgreSQL, Redis or Docker socket to the network.

## Existing Milestone 0 deployments

Do not overwrite the existing .env or database volumes. Keep POSTGRES_PASSWORD
unchanged, copy the old operator DATABASE_URL into MIGRATION_DATABASE_URL, generate
APP_DATABASE_PASSWORD, and set DATABASE_URL to cisrice_app with the runtime password.
Rebuild/start Compose. See docs/operations/deployment.md for the upgrade procedure.

## Development and verification

Reference tools: Python 3.12 and Node 24; Python 3.14/Node 26 have also been exercised
where recorded in STATUS.md. On Arch with uv:

    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python -e './backend[dev]'
    cd frontend
    npm ci
    npm run lint
    npm run format:check
    npm test
    npm run build
    npx playwright install chromium --only-shell
    cd ..
    .venv/bin/python infrastructure/scripts/verify_linux.py --e2e

The verifier requires the running stack and private .env. It uses Linux bridge
addresses, creates a unique disposable database, provisions restricted runtime
privileges, tests migrations and APIs, runs isolated browser servers on 18000/14173,
then removes only the test database and stops the temporary servers. Use --skip-live
to test changed code before updating the running API. It is not a Docker Desktop verifier.

AGENTS.md lists backend lint, formatting, type and test commands. Host API development
needs explicitly reachable DATABASE_URL/REDIS_URL values; Compose hostnames in .env
are container names. Vite proxies /api to localhost:8000 by default; CISRICE_API_URL
overrides that target for isolated test servers. Cookie sessions/CSRF tokens are never
stored in localStorage.

## Security and limits

Passwords use Argon2id. Session tokens are random, HttpOnly, SameSite=Strict, stored
only as digests in PostgreSQL. Writes require a trusted Origin and session-bound CSRF
token. The application role cannot create databases/schema or rewrite audit records.
Only migrations receive operator credentials. .env belongs outside Git and backups
must protect it. No provider credential-encryption key exists because provider secrets
are not stored yet; an externally keyed vault is required before adding token storage.

Provisioning is operator-only: no public signup, invitation email or self-service
password reset. Portfolio UI lists show up to 200 records per collection; API
pagination is available. Account URLs are stored references, not fetched or verified.
Publishing, media acquisition, inference and analytics are not implemented yet.

Default HTTP cookies are appropriate only for localhost/SSH-tunneled use. Set
COOKIE_SECURE=true with explicit ALLOWED_HOSTS/ALLOWED_ORIGINS JSON arrays before a
separately configured TLS deployment. Redis failure blocks login and business writes;
authenticated logout still revokes the PostgreSQL session after Origin/CSRF checks.

The existing MIT license is preserved. Third-party distribution compatibility,
remote CI outcomes, Windows container deployment and backup/restore remain separate
verification items. See STATUS.md, IMPLEMENTATION_PLAN.md and docs/adr.

## Discovery
Select a brand, open Discovery, and add a permitted publisher's final HTTPS RSS/Atom
URL or a YouTube channel ID (UC followed by 22 characters). Record the source policy
and confirm research use is allowed. Set keywords, source quality and optional
scoring weights, then click Discover. Check the run history for failures.
Review/filter candidates, save notes, and copy candidates to another authorized
brand. Research approval does not approve media reuse; rights remain UNKNOWN.
Research opens the same inbox. No social account connection is needed for feeds.

Discovery is manually triggered and synchronous, with a 60-second source cooldown,
200 sources per brand, 200 entries and 2 MiB per run. Feed redirects, compression,
non-HTTPS fetching and private networks are rejected. Source policy acknowledgement
does not establish redistribution rights. Existing imported data is available offline.
See docs/api/discovery.md for contracts, scoring and deferred capabilities.
