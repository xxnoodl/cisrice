# Browser workflow tests

The workflow is in frontend/e2e/portfolio.spec.ts for frontend package resolution.
Run the Linux verifier with --e2e to provision isolated fixture credentials and servers.
It tests login, workspace/niche/two-brand creation, style saving, account registration,
independent brand context, reload and logout. It uses no live provider accounts.
Component and API authorization tests run separately. Never target a live account DB.

Future scenarios: discovery fixtures, acquisition, renders, approvals, explicit mock
publishing and evidence-labeled analytics, as their milestones land.

M2 extends the isolated workflow through source setup, fixture-feed discovery,
candidate approval/filtering and copying to a second brand with a paused source.
Only backend/tests/browser_app.py injects feed fixtures; production uses real HTTPS.
No real portfolio, platform accounts or external publishing is used by browser tests.

M3 extends the isolated workflow through rights approval, acquisition via an isolated
real Redis/Celery worker/dispatcher, local generated-video validation and protected
download. Transport substitution lives only in backend/tests/acquisition_worker_app.py.
Production has no fixture mode. Additional backend tests exercise the actual yt-dlp
CLI, CONNECT proxy and HTTPS client against an owned TLS video fixture.
