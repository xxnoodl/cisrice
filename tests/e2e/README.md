# End-to-end acceptance

M0 Compose smoke checks run in CI: API readiness, served dashboard HTML, worker ping.
Browser rendering and navigation must additionally be verified before acceptance.
The built frontend was smoke-checked in installed headless Edge for / and /operations
on 2026-10-25. To reproduce: start API on :8000, run `npm run build` and
`npm run preview` in frontend, then from root run:
```
python infrastructure/scripts/browser-smoke.py /absolute/path/to/chromium
```
Pass the installed Edge executable on Windows. This asserts mounted health/navigation
elements, not interaction behavior or healthy dependencies. It downloads no browser.
Future Playwright workflows will cover portfolio, fixture discovery/acquisition,
local rendering, approvals, explicit mock publishing and evidence-labeled analytics
as those features land. No live account publishing is authorized by tests.
