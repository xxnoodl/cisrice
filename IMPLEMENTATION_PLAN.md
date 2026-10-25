# Implementation plan

| Milestone | Deliverables / acceptance | State |
|---|---|---|
| 0 | Monorepo, Compose, API/UI, PostgreSQL/Redis health, migration, CI; real startup and tests pass | Implemented; deployment verification blocked |
| 1 | Secure authentication, portfolio hierarchy, backend authorization and audit; reject unauthorized access | Pending M0 acceptance |
| 2 | RSS/YouTube discovery, scored deduplicated candidate inbox and brand routing | Planned |
| 3 | Rights gates, safe acquisition, validation, deduplicated media storage | Planned |
| 4 | Local transcription/model adapters, deterministic analysis and feedback | Planned |
| 5 | Versioned manifest, inherited templates, replaceable FFmpeg rendering, QC and approval | Planned |
| 6 | Publishing state machine, scheduling, official adapters/manual handoff, reconciliation | Planned |
| 7 | Defined observations, separate predictions, evaluations, experiments | Planned |
| 8 | Resource controls, recovery, tested backup/restore, Linux and Windows packaging | Planned |

Dependencies follow this order. M0 remaining: run Compose on Linux and Docker Desktop/WSL2,
verify container-served dashboard and Celery worker startup, execute real migration round trip
and service integration tests. Do not advance to M1 before acceptance.
