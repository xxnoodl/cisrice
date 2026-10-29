# Implementation status

Milestones 0–3 are complete and accepted on native Linux (2026-10-29).
Next milestone: 4, local intelligence.

## Implemented
- FastAPI/React/PostgreSQL/Redis/Celery foundation, migrations, health and CI.
- Argon2id local login, opaque sessions, CSRF, rate limits and scoped authorization.
- Portfolio hierarchy, brand settings, platform registration, permissions and audits.
- Brand-scoped RSS/Atom/YouTube topic discovery, scoring with missing signals,
  deduplication, candidate review/notes and explicit brand routing.
- Human rights decisions, revocation and acquisition gates; no inferred permissions.
- PostgreSQL durable jobs, cancellation, expiring leases, fencing, bounded retries,
  immutable worker contracts and a polling dispatch outbox. Redis carries IDs only.
- Bounded DNS-pinned HTTPS streaming and restricted yt-dlp resolution; no auth/cookies,
  DRM, playlists, external downloaders or remote JavaScript components.
- Local ffprobe/FFmpeg validation, quarantine, SHA-256 immutable storage, protected
  media library/downloads and authorized cross-brand reuse.
- Configurable quotas/free-space/file-size/temporary retention. Cleanup defaults to
  dry run and never deletes canonical media or database records.
- Dispatcher/storage-init services, shared media volume, capability restrictions and
  append-only media database grants. Live container checks passed below.

## Verified application acceptance
- Durable-job prerequisite passed 29 backend tests and migration round trip before
  business Celery tasks were registered.
- 43 backend tests pass with real PostgreSQL/Redis, generated owned video and real
  FFmpeg/ffprobe, including rights/access revocation, cancellation, disk failure,
  quarantine, deduplication, reuse and protected runtime database permissions.
- Actual yt-dlp 2026.10.26 subprocess, CONNECT proxy and HTTPS download verified against
  a generated owned TLS fixture. Test DNS/routing/trust are explicitly substituted;
  no live account or third-party media is used.
- Seven frontend component tests and two Playwright tests pass. The latter execute
  portfolio/discovery/rights review, a real isolated Celery job, validation and download.
  Browser-worker network bytes are an explicitly labeled generated fixture.
- Disposable migration upgrade/check/downgrade/re-upgrade/check and post-upgrade
  integration test pass through revisions 0004 and 0005. Application DB never downgraded.
- Ruff lint/format, strict mypy, frontend lint/format/TypeScript/build pass.
- pip check passes; pip-audit retry reports no known vulnerabilities. The local
  unpublished project itself is skipped. Dependency/license inventory updated.
- Cancellation queries apply workspace/brand filters before locking; a locked job in
  another brand cannot block or influence cancellation. The full 43-test run passed.

## Verified deployment acceptance
- A pre-upgrade pg_dump archive is saved privately under data/backups; pg_restore
  archive listing was verified. Actual restoration is NOT tested.
- Initial combined build hit npm ETIMEDOUT and cancelled backend installation.
  Builds now use pip/npm cache mounts and bounded retries, and run sequentially.
- Existing application data and Docker volumes are preserved. No public publication,
  live-account automated test or destructive cleanup of real media occurred.
- Sequential backend/frontend image builds and final Compose startup passed.
- Live readiness on 8000/8080, registered acquisition task, worker ping, operator
  retention dry run and deployed public browser smoke passed.
- Exact deployed source was checked for scoped cancellation and disabled geographic
  bypass. The final full verifier passed 43 backend tests, two isolated browser
  workflows, migration round trip and live health/worker checks.
- Worker runs as uid 10001 with CapEff zero. Actual shared-volume write, read-only
  hardlink, ffprobe and full FFmpeg decode passed using a temporary owned fixture;
  no fake media references or users were added to the application database.
- Runtime schema is 0005, role cisrice_app; canonical object UPDATE is denied.
  Operator migration credentials are absent from API environment. Existing user,
  workspace and brand records were preserved.
- Container FFmpeg is 7.1.5-0+deb13u1; yt-dlp is 2026.10.26. Exact deployed Python
  requirements audit reports no known vulnerabilities; npm audit reports zero.
- Backup archive listing only was verified; no restore guarantee is claimed.

## Limitations and deferred work
- No OAuth/token vault, model inference, production, publishing or analytics yet.
  Registered platform accounts are not connected accounts.
- Public-platform download availability is unverified/capability-dependent; no bypass
  of authentication, paywalls, DRM or restrictions is supported.
- No uploads, segmented/adaptive extraction, canonical garbage collection or automatic
  destructive retention scheduler. Canonical originals/audit records are retained.
- Job retry/recovery tests simulate expired leases; the broad actual process-kill,
  database/Redis restart matrix and verified backup restoration remain M8 work.
- Source editing/deletion, automatic/autonomous discovery, semantic clusters, additional
  source/API adapters and large-history UI pagination remain deferred.
- Local provisioning only; no invitations or self-service password recovery yet.
- Windows/WSL2 deployment, GitHub-hosted CI execution and complete distribution/image
  license compatibility review remain unverified. Existing MIT license is preserved.
- Native Linux through SSH is the user's preferred workflow; WSL is not required.
- Docker service boot auto-start is not configured. Upstream TestClient deprecation
  warning remains non-fatal.

Next: M4 local transcription/intelligence with graceful optional-dependency handling.
