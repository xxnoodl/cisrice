# Rights-aware acquisition and media API

All paths use /api/workspaces/{workspace}/brands/{brand}/media.
Authentication and backend brand authorization apply to every operation. Mutations
require editor/owner access, trusted Origin, X-CSRF-Token and normal write limits.

- GET /rights?offset=0: latest 50 rights decisions; page with offset.
- POST /rights: candidate_id (optional, must be approved research in this brand),
  title, HTTPS source_url, adapter=direct/ytdlp, basis=OWNED/LICENSED/PERMISSION,
  license, evidence, attribution, restrictions, confirmed=true.
  This records a human decision, not an automated legal determination.
- POST /rights/{id}/revoke: revoke a decision; evidence/audit records remain.
- POST /requests: rights_id and UUID idempotency_key; HTTP 202 queues a durable
  acquisition request. Unknown or revoked rights cannot be queued.
- GET /jobs?offset=0: latest 50 durable job summaries, no payload or lease secret.
- POST /jobs/{id}/cancel: cooperative cancellation; terminal jobs remain unchanged.
- GET /assets?offset=0: paginated brand references and validated media metadata.
- GET /assets/{id}/file: authorized media download/range response; revoked rights
  block access. No global hash/path endpoint is exposed.
- POST /reuse: source_brand_id, source_asset_id, destination_rights_id. Requires
  editor access to both brands and active rights covering the same source URL.
  Creates a destination reference without copying bytes.

Research approval alone never grants acquisition rights. Missing rights are UNKNOWN;
only explicit confirmed rights decisions enter the queue. Decisions are immutable
apart from revocation; create a new decision to correct evidence or scope.
Restrictions/attribution are recorded for later production/publication review;
Cisrice does not infer their legal meaning or automatically publish content.

## Job and storage contracts
Job payload v1 contains only rights_id. PostgreSQL owns QUEUED/RUNNING/RETRY/
SUCCEEDED/FAILED/CANCELLED, attempt budget, cancellation, correlation and lease.
The polling dispatcher redelivers unclaimed/expired work; Redis carries UUIDs only.
Claims have 45-second leases with heartbeats, a three-attempt default budget and
fenced atomic output registration/completion. At-least-once execution is intentional.
Retries use exponential backoff; Retry-After up to one day is respected. Longer
server waits fail for manual resolution rather than retrying early.
Progress resets for a new attempt. Cancellation and current actor/rights checks
run during work and again before completion. Publishing will need its own separate
remote-state reconciliation; acquisition does not authorize publication.

One database-wide acquisition/validation slot prevents competing heavy downloads.
Staging is unique per job/lease. Metadata resolves at most one direct HTTPS video;
no authentication, cookies, geographic bypass, DRM, playlists, live streams, segmented formats,
external downloaders or JavaScript runtime/components are enabled.
The resolver uses a bounded public-address CONNECT proxy, system certificate trust,
60-second/4-MiB stdout limits and no configuration/plugins. Signed selected-format
URLs stay ephemeral and are not logged or stored.

Native streaming validates DNS answers and pins a public address on every redirect
hop (maximum three followed redirects); HTTPS only, default port, no credentials,
compression or private/reserved/transition-address destinations. Socket timeout is
8 seconds; transfer budget 300 seconds plus current socket operation. OS DNS timing
is system-managed. No proxy environment is inherited.

Limits: default 512 MiB/file, 20 GiB logical media quota and 512 MiB minimum free.
Maximum-size preflight reservation is conservative. ffprobe permits local MP4/
Matroska/WebM video only; dimensions <=7680, duration <=7200 seconds. FFmpeg performs
full CPU decode with a 120-second timeout. These checks establish technical validity,
not creative quality. Audio presence/codecs are retained as observed metadata.
Canonical files use objects/sha256/ab/cd/HASH.extension, atomic no-overwrite links,
read-only permissions and SHA-256 deduplication. Canonical metadata and brand links
are append-only for the runtime database role. Corrupt canonical objects fail closed.
Invalid media enters quarantine. Source objects and audit records are never purged.

## Retention and recovery
STAGING_RETENTION_HOURS defaults to 24; QUARANTINE_RETENTION_DAYS defaults to 0
(preserve). Zero disables the corresponding cleanup. Operator-only command:
    docker compose exec worker python -m app.modules.acquisition.maintenance cleanup
This is a dry run. Add --apply only to delete eligible old terminal-job temporary
locations. Active/unknown jobs, symlinks, canonical objects and database records are
never deleted. Purge intent/completion are audited. At most 200 entries per class
are inspected per invocation; there is no automatic destructive scheduler.

A crash can leave a canonical file before its database registration; future imports
deduplicate it. No automatic canonical garbage collection is attempted, because
future project/audit references must be respected. A full backup restore and actual
process-kill/database/Redis restart matrix remain Milestone 8 acceptance work.

## Verified scope / limitations
Tests use generated owned media, real FFmpeg/ffprobe and an actual yt-dlp subprocess
through an isolated TLS fixture. Browser tests use real Redis/Celery and an explicitly
substituted transport for the same owned clip, not live accounts or outside media.
No particular public platform's download availability is guaranteed: current API,
format and source restrictions can require manual workflow or a future adapter.
OAuth, authenticated acquisition, file uploads, subtitle acquisition and production
are not included. Failed/corrected acquisitions can be submitted with a new rights
decision/request; automatic retries are bounded. UI rights/job histories show 50 rows;
the API supports pagination.
