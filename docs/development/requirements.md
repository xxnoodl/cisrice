# Deferred requirement register

The master product specification remains the product contract. This foundation does
not implement later milestones. The table records required work rather than implying
that reserved modules constitute completed functionality.

| Milestone | Required scope retained |
|---|---|
| 1 | Users, hashed passwords, secure sessions/CSRF, workspace memberships, niches, brands, account permissions, style guides, registered/connected/expired/restricted states, context switching, audit, backend isolation, least-privilege runtime DB role |
| 2 | Bounded source policy/quotas, RSS/Atom and YouTube feeds, permitted Reddit/podcast interfaces, provenance, source observations/subscriptions/runs, fingerprints, topic clusters/recommendations, candidate routing/review/notes, configurable available-signal scoring (25/20/15/10/10/10/10), missing indicators; rights gate separate |
| 3 | Human rights evidence/review, safe yt-dlp inspection/acquisition, SSRF/DNS/redirect defenses, cancellation/retries/progress, staged validation/quarantine, immutable SHA-256 objects, authorized brand links, export naming, quotas, retention and reference-aware deletion |
| 4 | Optional tiered deterministic/audio/embedding/local-model analysis, model registry/router/cache/resource records, Ollama and whisper.cpp dependency handling, timestamped editable transcripts, classifications, clips, suggestions, structured feedback; no autonomous retraining or factual-verification claims |
| 5 | Versioned manifest/migrations, explicit global→niche→brand→platform→variant overrides, replaceable renderer protocol, FFmpeg CPU fallback, preview/final queues/cancel/progress/history, parameter editor, subtitles/text/crop, technical QC and human approval |
| 6 | Real capability-aware OAuth adapters, encrypted tokens with key outside DB, state machine and validated transitions, timezone/DST calendars/windows/pauses, account locks/idempotency/backoff/budgets, attempts/dead letters, ambiguous-state reconciliation, approved manual handoff packages and external-URL confirmation; no invented API access |
| 7 | Scoped portfolio-to-content analytics, versioned metric definitions/windows/units/denominators/provenance, unavailable ≠ zero, separate OBSERVED/PREDICTED/EXPERIMENTALLY VALIDATED displays, immutable forecast history, baseline insufficient-data results, calibrated evaluation, evidence-linked recommendations and experiment design/limitations |
| 8 | Resource coordinator, concurrency/priorities/GPU detection and CPU fallback, durable worker heartbeats/jobs/outbox/idempotent consumers, structured monitoring, offline cache/resumability, partition/failure recovery, verified backup+restore including keys/media/manifests/config, Linux and actual Windows/WSL2 deployment validation |

Durable jobs/outbox and authorization must be introduced as prerequisites to the first
business background jobs, not postponed until reliability work. Security validation,
tests, documentation and database migrations accompany each milestone. No external
publishing, paid APIs or account actions are authorized implicitly by a test fixture.
