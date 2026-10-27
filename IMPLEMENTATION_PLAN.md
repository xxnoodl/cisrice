# Implementation plan

| Milestone | Deliverables / acceptance | State |
|---|---|---|
| 0 | Monorepo, Compose, API/UI, PostgreSQL/Redis health, migration, CI; real startup and tests pass | Complete on native Linux; Windows/WSL2 unverified |
| 1 | Secure authentication, portfolio hierarchy, backend authorization and audit; reject unauthorized access | Complete on native Linux |
| 2 | RSS/YouTube discovery, scored deduplicated candidate inbox and brand routing | Planned |
| 3 | Rights gates, safe acquisition, validation, deduplicated media storage | Planned |
| 4 | Local transcription/model adapters, deterministic analysis and feedback | Planned |
| 5 | Versioned manifest, inherited templates, replaceable FFmpeg rendering, QC and approval | Planned |
| 6 | Publishing state machine, scheduling, official adapters/manual handoff, reconciliation | Planned |
| 7 | Defined observations, separate predictions, evaluations, experiments | Planned |
| 8 | Resource controls, recovery, tested backup/restore, Linux and Windows packaging | Planned |

Dependencies follow this order. Native Linux M0 acceptance passed: Compose startup,
container-served browser rendering, worker ping, real-service tests and migration
round trip. Windows/WSL2 remains explicitly unverified. M1 acceptance also passed; proceed to M2 next.

Initial Linux checks on 2026-10-27 passed before Docker setup (8 tests passed;
1 service test skipped). The deployment follow-up below supersedes that checkpoint.

2026-10-27 deployment follow-up: M0 accepted on native Linux; all 5 backend tests
passed with real services, migration round trip passed, and container-served browser
smoke passed. The repeatable verifier uses a disposable database.

2026-10-27 M1 acceptance: 18 real-service backend tests, 7 frontend component tests,
2 isolated browser tests, deployed browser smoke, quality gates and migration round trip passed.
