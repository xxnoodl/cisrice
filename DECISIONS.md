# Decisions

The ten initial ADRs in docs/adr are authoritative foundation decisions.
Use Python 3.12 in containers and CI; local 3.14 is additionally exercised where possible.
Use Node 24, React 19, Vite 7.3, React Router 7 and TanStack Query 5. npm lockfile pins
the resolved frontend graph; Python direct ranges constrain compatible releases.
ESLint 10 is selected after the installation warning and official support table
confirmed ESLint 9 is end of life. typescript-eslint >=8.56 supports ESLint 10.
References: https://eslint.org/version-support/ and
https://typescript-eslint.io/users/dependency-versions/.
Vitest 5.0.5 replaces the initial 3.x selection after npm audit reported vulnerable
mocking/pool dependencies. Node 24 and Vite 7.3 satisfy Vitest 5 prerequisites.
Reference: https://vitest.dev/guide/.
Use plain CSS with semantic reusable React sections initially: small dependency surface,
visible keyboard focus, no inaccessible custom form controls. Revisit a component library
when identity forms/dialogs establish concrete needs.

Health is public and exposes only dependency names/status, never exception details.
Readiness requires both live services and the expected migration revision. Migrations
run in a dedicated one-shot container, never at API import. No fake users or accounts.
Storage directories and domain packages reserve structure only; no fabricated features.
PostgreSQL container owner is migration owner for M0; split runtime privileges before
business endpoints in M1. During GitHub integration, the destination repository already
contained an MIT license selected in its initial commit. Preserve that license and
copyright notice. This does not establish third-party dependency compatibility;
Redis server and GPL media tooling still need separate distribution review.

Native Linux continuation (2026-10-27): use an isolated uv-managed Python 3.12
environment on the Arch host rather than altering its system Python 3.14. Keep
Node 24 as the container/CI baseline; host Node 26.10 also passed current frontend
checks. Docker installation requires the operator's interactive sudo; do not collect
sudo passwords or weaken sudo policy for automation.

Deployment verification (2026-10-27): a Linux-only verification utility uses private
Docker bridge addresses from the host to run tests with the development environment.
It creates a UUID-named disposable database and never downgrades the application
database or publishes PostgreSQL/Redis host ports. This keeps test packages out of
runtime images. Runtime images remain constrained rather than digest-locked;
Windows/WSL2 validation is a separate, explicitly unverified deployment target.

Milestone 1: ADR 0011 records operator-only user creation, Argon2id, opaque PostgreSQL
sessions, CSRF/origin protection, explicit authorization and separate migration/runtime
database roles. No provider passwords/tokens are accepted. Browser acceptance uses
a disposable database and temporary servers, not the application database.

## Milestone 2 (2026-10-28)
ADR 0012 adopts brand-scoped RSS/Atom sources, explicit policy acknowledgement,
bounded DNS-pinned HTTPS fetches, synchronous atomic runs and URL deduplication.
YouTube uses the documented public channel topic feed; no OAuth/API claim.
Research notes consolidate initial findings; feed categories support topic filtering.
Routing copies provenance with fresh review state and paused destination sources.
Initial scores are reproducible editorial heuristics with missing signals preserved.
Durable asynchronous discovery, semantic clusters and autonomous exploration are deferred.

## Milestone 3 (2026-10-29)
ADRs 0013/0014 establish durable PostgreSQL jobs before download tasks, expiring
leases and immutable public job contracts; rights decisions gate queueing and output
registration. A polling dispatcher retains work across Redis delivery failures.
Direct streaming and a restricted yt-dlp metadata resolver share DNS-pinned public
HTTPS controls. FFmpeg reads local validated containers only. Canonical SHA-256
objects are immutable, globally deduplicated and exposed solely through authorized
brand references. Retention preserves canonical media and requires an operator to
apply temporary-file cleanup. Platform-specific acquisition remains capability-limited.
