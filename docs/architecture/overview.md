# Foundation architecture

Browser → nginx (same origin /api proxy) → FastAPI → PostgreSQL and Redis.
Celery worker uses Redis but currently has no application jobs. Future durable jobs
and transactional outbox live in PostgreSQL. Modules communicate through services,
typed contracts and explicit events. Source media will be immutable and content-addressed.

Only operations health is implemented. Empty package directories reserve domain names;
they do not constitute implemented domain coverage. Full product requirements are
tracked by milestones, with authorization preceding business APIs.
