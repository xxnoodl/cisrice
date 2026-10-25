# Dependency and licensing review

Repository license is pending owner choice and distribution audit. No compatibility
claim is made. Frontend lockfile captures resolved versions. Python packages use
constrained direct versions; exact deployed transitive versions remain unlocked.

Expected upstream licenses (must recheck installed metadata before distribution):
FastAPI/Pydantic/SQLAlchemy/Alembic/React/Vite: MIT; Celery: BSD; psycopg: LGPL;
PostgreSQL: PostgreSQL license; Redis 7.4: source-available RSALv2/SSPLv1 rather than
unconditionally OSI open source. Redis is retained to meet the explicit baseline;
revisit a compatible transport or separately licensed Redis version before packaging.
FFmpeg builds can carry LGPL/GPL obligations; current host reports a GPL build.
yt-dlp and model weights require independent review when introduced.

Run `npm audit`, `python -m pip_audit`, `npm ls --all` and inspect installed Python
metadata as part of release review. A vulnerability scan is not a license audit.
Image base licenses, transitive components, notices and model licenses remain pending.

Primary license references: https://redis.io/legal/licenses/ and
https://www.psycopg.org/docs/license.html. Record an actual resolved component
inventory before choosing the repository license.

python-inventory.json records the locally installed Windows/Python 3.14 graph and
declared license metadata (not a compatibility finding or Linux lockfile). Backend
pip-audit initially identified vulnerable pip 26.1.1; upgrading to 26.2.2 produced
"No known vulnerabilities found" on 2026-10-25. The local unpublished cisrice-backend
package is excluded by the audit provider and must be reviewed through source/tests.

Frontend initial Vitest 3 dependency graph had three audit findings (two critical).
Vitest 5.0.5 and supported ESLint 10 are now selected; final install reports zero
vulnerabilities. package-lock.json records resolved versions and declared licenses.
Neither npm nor pip audit evaluates source correctness or licenses for compatibility.
