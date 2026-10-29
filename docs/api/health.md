# Health contract

GET /api/health/live: 200 {status: ok, version: 0.1.0}. Does not require dependencies.
GET /api/health/ready: 200 when PostgreSQL SELECT 1, Redis PING and migration revision
0005 pass; otherwise 503 with status degraded. dependencies maps postgresql, redis,
schema to ok/unavailable. Errors are redacted. No credentials or private data.
Every API response has a server-generated X-Correlation-ID and nosniff header.
Health checking is synchronous with bounded connection/socket timeouts.
