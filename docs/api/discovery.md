# Discovery API (Milestone 2)

All routes use /api/workspaces/{workspace}/brands/{brand}/discovery.
Authentication and brand access are required. Writes require editor/owner, trusted
Origin and session-bound X-CSRF-Token; normal write rate limits apply.

- GET /sources: list up to 200 brand-owned sources.
- POST /sources: create name, kind (rss/youtube), address (HTTPS URL/channel ID),
  keywords (up to 20), quality (operator assessment, 0–1), seven weights,
  policy_note and policy_confirmed=true. Defaults follow the product weighting.
- POST /sources/{id}/toggle: pause/resume; does not fetch.
- POST /sources/{id}/runs: manually fetch/import; completed result is SUCCEEDED or
  FAILED. HTTP 201 means a run record was created, not that discovery succeeded.
  Read state/error. Cooldown 60 seconds per source; bounded to 200 entries/2 MiB.
- GET /runs?offset=0: newest 50 runs.
- GET /candidates: status=INBOX/APPROVED/REJECTED (omit for all), search (title),
  topic (exact publisher category), order=score/newest, offset (50 per page).
- PATCH /candidates/{id}: status and notes. This is research review, not rights approval.
- POST /candidates/{id}/route: target_brand_id in the same workspace; requires edit
  permission to both brands. Copies public source provenance, never private notes or
  review state; newly copied sources start paused. Repeating the copy deduplicates.

Candidate identity is SHA-256 of a conservatively normalized URL (host case/default
port/fragment only). Original URLs and source identifiers remain in observations.
Different URLs with the same normalized title show possible-duplicate indicators;
this is a heuristic, not media fingerprinting. Deduplication is brand-scoped.
Sources consolidate subscriptions: each is owned by one brand; routing creates an
explicit authorized destination reference rather than sharing private brand data.

Scores are immutable initial editorial heuristics, version deterministic-v1.
Relevance is keyword match fraction, freshness decays over 30 days, novelty is an
initial title match heuristic, quality is operator assessment. Engagement velocity,
shares and saves are unavailable. Normalize over present components; if configured
weights exclude all available signals, score is null. Weights are configurable at
source creation; historical scores are not silently recalculated. No confidence,
performance prediction or experimental validation is claimed.

Rights status is always UNKNOWN in discovery. Acquisition and publication need
separate eligibility/approval workflows. Summary HTML is displayed as text, never
executed. No enclosure, thumbnail or media download happens.

Scope: RSS 2.0 and Atom only; HTTPS/default port; reject credentials, redirects,
compression and any DNS answer containing private/reserved/multicast or supported
IPv6 transition targets. Pin one validated IP while retaining TLS hostname checks.
Socket timeout is 8 seconds, body transfer budget 15 seconds plus the current socket
read; OS DNS resolution timeout is system-managed. No proxy environment is used.

Runs are synchronous and atomic: a process crash rolls the transaction back; no
background-job durability or crash-history guarantee is claimed. Normal transport/
parse failures commit a FAILED run and can be retried after cooldown. Cached research
remains readable offline. No automatic polling, crawler, recommendations, semantic
topic clustering, YouTube OAuth/API access, Reddit adapter or scheduled discovery yet.
Topic filtering uses publisher categories, not inferred factual classification.

YouTube adapter follows the documented channel topic URL:
https://developers.google.com/youtube/v3/guides/push_notifications
This implementation reads the feed; it does not subscribe to WebSub.

Source configuration is set at creation; in-place editing, deletion and rescoring are
deferred. Pause a source to stop discovery. Candidate lists paginate; source registry
is capped at 200 and UI history shows 50 runs (older runs remain API-accessible).
