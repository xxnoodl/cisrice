# Identity and portfolio API (Milestone 1)

Portfolio routes require a valid HttpOnly session cookie. Writes also require an
exactly allowed Origin and the X-CSRF-Token returned by login/session. No CORS access
is enabled. JSON requests are limited to 64 KiB, including streamed bodies. Validation
errors omit supplied input values. List endpoints accept limit (1–200) and offset.

Public/auth routes:
- GET /api/auth/status: whether the local operator needs to create a user.
- POST /api/auth/login: email/password JSON; returns user, csrf_token, expires_at and
  sets cisrice_session. Generic invalid-credential errors; failures are audited.
- GET /api/auth/session: authenticated user and session-bound CSRF token.
- POST /api/auth/logout: revokes the database session and clears the cookie.

Portfolio:
- GET/POST /api/workspaces.
- GET/POST /api/workspaces/{workspace}/niches.
- GET/POST /api/workspaces/{workspace}/brands.
- GET/PATCH /api/workspaces/{workspace}/brands/{brand}.
- GET/PUT .../brands/{brand}/style-guide.
- GET/POST .../brands/{brand}/accounts; GET/PATCH .../accounts/{account}.
- GET/PUT .../members; DELETE .../members/{user_id}.
- GET/PUT .../brands/{brand}/permissions; DELETE .../permissions/{user_id}.
- GET/PUT .../accounts/{account}/permissions; DELETE .../permissions/{user_id}.
- GET .../audit (workspace owner); GET .../brands/{brand}/audit (authorized brand user).

Owners manage all contained brands/accounts and permissions. Members see only
explicitly granted brands; viewers cannot write. Accounts need a separate account
grant, and account writes need both brand editor and account editor permission.
Revoking a brand also removes its account grants. The last owner cannot be removed
or demoted. Unauthorized scopes return 404; insufficient in-scope roles return 403.

New platform accounts always have REGISTERED status. Clients cannot mark accounts
connected or submit provider passwords/tokens. The schema reserves CONNECTED,
NEEDS_AUTHORIZATION, EXPIRED, RESTRICTED and DISCONNECTED for later adapters.
Profile URLs are stored references only; no requests or rights claims are made.

Changes and authentication events are audited transactionally. Runtime privileges
permit audit INSERT/SELECT, never UPDATE/DELETE. This is an application audit trail,
not tamper-proof storage against the database operator.

Authenticated logout retains Origin/CSRF protection but bypasses the Redis rate
bucket so the authoritative PostgreSQL session can be revoked during a Redis outage.
Business writes and login continue to fail closed. FastAPI >=0.121 is required for
function-scoped transaction dependencies that finish before the response is sent.
