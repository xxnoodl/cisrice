# Decisions

The ten initial ADRs in docs/adr are authoritative foundation decisions.
Use Python 3.12 in containers and CI; local 3.14 is additionally exercised where possible.
Use Node 24, React 19, Vite 7.3, React Router 7 and TanStack Query 5. npm lockfile pins
the resolved frontend graph; Python direct ranges constrain compatible releases.
ESLint 10 is selected after the installation warning and official support table
confirmed ESLint 9 is end of life. typescript-eslint >=8.56 supports ESLint 10.
References: https://eslint.org/version-support/ and
https://typescript-eslint.io/users/dependency-versions/.
Vitest 5.0.5 replaces the initial 3.x selection after npm audit reported vulnerable
mocking/pool dependencies. Node 24 and Vite 7.3 satisfy Vitest 5 prerequisites.
Reference: https://vitest.dev/guide/.
Use plain CSS with semantic reusable React sections initially: small dependency surface,
visible keyboard focus, no inaccessible custom form controls. Revisit a component library
when identity forms/dialogs establish concrete needs.

Health is public and exposes only dependency names/status, never exception details.
Readiness requires both live services and the expected migration revision. Migrations
run in a dedicated one-shot container, never at API import. No fake users or accounts.
Storage directories and domain packages reserve structure only; no fabricated features.
PostgreSQL container owner is migration owner for M0; split runtime privileges before
business endpoints in M1. No repository license grant until dependency audit and owner
choice. Redis server and GPL media tooling need separate distribution review.
