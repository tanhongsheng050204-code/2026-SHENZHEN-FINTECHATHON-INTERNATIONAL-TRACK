# Plans 2 and 3 review and deployment handover

Reviewed on 2026-10-09, including the newer finance, agent, Passport and web
changes merged from origin/main. This is local execution evidence; hosted
Supabase authentication and the production backend still need deployment access.

## Fixes

- Added the missing tenant column to structured ingestion batches, including
  SQLite upgrade handling and scoped PostgreSQL application/worker policies.
- Kept each session's CSRF token stable across session reads, provider token
  refresh and MFA verification. Auth responses are not cached.
- Required recent MFA for password recovery when the provider account has an
  enrolled factor. Future or expired MFA timestamps cannot satisfy recovery.
- Removed password/CSV inputs from authentication and import validation errors.
- Preserved custom position names when applying an industry template, and
  returned position changes in the agreed job-function order.
- Deduplicated alert recipients and kept last-Owner guard behavior consistent.
- Provisioned the global vault key on the trusted startup connection before
  imports enter the application role. A PostgreSQL advisory lock serializes
  concurrent startup. Application users still cannot create encryption keys.
- Updated two vulnerable frontend transitive dependencies without a major update.
- Kept the original Plan 1 contract frozen; current API drift is checked against
  `docs/api/topic-e-current-contract.json`.

## Checks

- Full backend suite after merging the remote work: 447 passed, 1 skipped.
  The PostgreSQL integration check was enabled for this run. The remaining skip
  requires live model credentials and was not executed.
- Added session/recovery/import regression tests with mocked provider responses.
  No provider emails or external model calls were made.
- Applied all 34 real SQL migrations to a fresh local PostgreSQL 17 database
  with pgvector and a minimal Supabase auth schema bootstrap.
- Ran all eight import schemas through the real PostgreSQL application role.
  Checked tenant isolation, payroll line/vault denial for Finance without HR,
  the last-Owner trigger and the settings security tightening trigger.
- Offline evaluation: 30 tasks passed.
- Ruff, frontend lint, TypeScript/Vite build and web hardening checks passed.
  Frontend lint retains 14 existing warnings.
- npm audit and pip-audit reported no known dependency vulnerabilities.

The optional PostgreSQL test runs with `FINBRAIN_REVIEW_POSTGRES_URL` against a
dedicated disposable database. It rolls back its synthetic records. The ordinary
SQLite job skips it; a separate PostgreSQL CI job applies all migrations and runs
it. `scripts.check_plan23_migrations` bootstraps and applies
migrations to the explicitly named local review Docker container; use an empty
review database for that command.

## Hosted deployment requirements

The repository has a Cloud Run + Vercel runbook in
`docs/deployment/cloud-run-and-vercel.md`. Before serving the new backend:

1. Connect the intended Cloud Run project/service and the Supabase project.
2. Apply the new Plan 2 and Plan 3 migrations to that database.
3. Deploy the backend with the existing independent encryption secrets and
   Supabase server credentials; do not replace existing vault keys.
4. Point Vercel's `BACKEND_ORIGIN` at the backend and validate `/api/health`
   returns backend JSON, and signed-out protected routes return 401.
5. Complete hosted OTP, TOTP, recovery, invitation and CSV upload checks before
   changing `VITE_AUTH_MODE` to `backend`.

The accessible `finbrain-topic-e-preview` Vercel project is a preview. Publishing
that frontend alone does not deploy the Plans 2 and 3 backend or SQL migrations.
