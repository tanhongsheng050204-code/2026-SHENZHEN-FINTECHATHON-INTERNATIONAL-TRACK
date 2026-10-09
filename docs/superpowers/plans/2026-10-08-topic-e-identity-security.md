# Plan 2 — Identity and security

Implementation date: 2026-10-08. Workstream: B1.

## Status and scope

Backend implementation is committed and covered by regression/database checks.
The current completion ledger is `docs/REMAINING_WORK.md`; hosted authentication
rehearsal remains pending. This replaces Plan 1's Team, settings,
Trust, message-template, alert-rule and kill-switch stubs with database services.
The finance engine, import mappings, persisted agent runs/inbox/workspaces and
external grants remain with Plans 3–6. Authentication screens are Plan 8.

The frozen Plan 1 business request/response models and paths remain. The replaced
routes return `data_mode="live"`. The agent list returns configured manifests and
persistent stop states; proposal metrics are `null` until Plan 5 records real ones.
Runs, autonomy changes, inbox actions and workspace calculations still identify
themselves as stubs. A live security control does not imply a live agent runtime.

## Implemented components

| Component | Implementation | Behavior |
| --- | --- | --- |
| Backend Supabase Auth | `backend/app/auth/provider.py`, `routes/auth.py` | Password, signup, email code, invite acceptance, recovery, TOTP enrol/challenge/verify; provider bodies and tokens are not forwarded |
| Sessions | `auth/sessions.py`, `auth/dependencies.py` | Random opaque cookie; hashed handle/CSRF secret; AES-GCM encrypted provider credentials; server refresh; fixed expiry; tenant idle timeout; revocation generation |
| MFA and disclosure | `auth/dependencies.py`, `security/detokenize.py` | Mandatory AAL2 for privileged roles and any extra tenant roles; five-minute step-up for sensitive operations; protected values masked without recent MFA |
| Team and job functions | `services/identity.py`, `routes/team.py` | Tenant memberships; masked emails; invitations; updates; last-owner protection; session revocation; database job functions used by inbox/workspace authorization |
| Settings | `services/tenant_settings.py`, `services/settings_catalog.py` | Schema validation, explicit previews, immutable versions, persisted proposals, distinct Compliance reviewer, version conflicts, rollback, industry templates |
| Customization | `services/customization.py` | Persisted template drafts/Owner approval and alert rules; existing placeholder/PII validation; critical cash rules retain an Owner recipient |
| Guardrails | `security/guardrails.py`, `services/ingestion.py` | English/Malay/Chinese patterns, Unicode normalization, quarantine before model enrichment, recorded ASI events and workflow-chain events |
| Agent controls | `services/agent_security.py`, `services/agent_catalog.py` | Global/per-agent kill switch, static skill allowlist, tenant agent identities, daily atomic tool/cost budget accounting |
| Trust | `services/trust.py` | Actual member/MFA activity, persisted guardrail events, tenant audit-chain verification, active vault generation; no fabricated attack counts |
| Database | `supabase/migrations/202610080001_identity_security_settings.sql` | Forced RLS, app-role secret restrictions, Team/settings policies, safety-floor constraints and triggers |

## Browser authentication protocol

Use an HTTPS API hostname under the same parent domain as the app. Cookies are
host-only with `HttpOnly`, `Secure`, `SameSite=Lax`, and `Path=/`.

Every browser request uses `credentials: "include"`. Every state-changing request
must carry the exact configured `Origin`. Once a session exists it also carries
`X-CSRF-Token`, obtained from the initial flow response or `GET /auth/session`.
The CSRF token is intended for browser JavaScript; provider credentials are not.
`GET /auth/session` rotates the CSRF token, so retain its latest value across tabs.

1. `POST /auth/sign-in` with email/password returns `email_code_required` and a
   CSRF token. Each sign-in requires an email code; remembered-device bypass is
   not implemented.
2. `POST /auth/email/verify` with the email code advances the same cookie session.
   The verified subject must match the password-authenticated subject.
3. `GET /auth/mfa/factors` lists only TOTP factor IDs/statuses. Choose an existing
   factor, or call `POST /auth/mfa/enroll` to receive the QR/secret once.
4. `POST /auth/mfa/{factor_id}/challenge` returns `challenge_id`.
5. `POST /auth/mfa/verify` with factor ID, challenge ID and code records recent MFA.
   Supabase's signed JWT must have `aal2`; client claims cannot elevate the session.
6. Reuse challenge/verify for step-up when an operation returns `step_up_required`.

New owners use `/auth/sign-up` → email verification → TOTP → `/auth/company` with
company name and slug. Company setup creates the tenant, first Owner membership
and version-1 settings atomically. Initial Trading settings are editable defaults.

Invitations originate from `POST /team/invitations` by an Owner with recent MFA.
Invitees start `/auth/invitation`, verify the invitation code and set a password
at `/auth/password`, then enroll/verify TOTP when their role requires it. An active
membership does not grant access until the session has verified email/password/MFA.

Recovery uses `/auth/recovery` → email code → `/auth/password`. An existing TOTP
account must challenge/verify its factor before the password update because Supabase
requires AAL2 for that operation. The API maps that provider refusal to
`step_up_required`. Changing the password
revokes other backend sessions and clears this session's prior MFA verification.
Privileged users must verify TOTP again. Sign-out revokes locally before attempting
provider logout, so provider downtime cannot keep an API session usable.

`GET /auth/me` retains the existing response shape but returns a masked email.
The session response includes tenant, role, job functions, AAL and onboarding state.
The first active tenant membership is selected; a multi-tenant switcher is not built.

## Settings rules

- The backend fetches role/job assignments from the database on every request.
- Owner proposes changes; security changes remain pending until a different
  Compliance user with recent MFA approves them.
- An approval applies exactly the proposed document. A changed base version returns
  `settings_version_conflict`; resubmit after reviewing the current version.
- Idle timeout can decrease, never increase. Required MFA roles can expand, never
  shrink. Mandatory privileged roles, critical alerts and the Owner recipient remain.
- Rollback creates a new version. It cannot loosen security. A security-changing
  rollback still requires a separate Compliance approval.
- Team permission changes increment the member's session generation, invalidating
  old sessions on the next request. The last active Owner cannot be removed.

## Privacy and runtime integration

Employee records use `payroll_line`, `employee_record`, or `leave_record`. Their
tokens have a namespace per employee source, distinct from customer/business tokens,
so an equal salary and invoice amount cannot share a token and disclosure policy.
The vault/registry persist `employee_personal`; Owner/HR access still requires recent
MFA. Other people see bands/masks. Plan 3's payroll importer must use this vocabulary
and pass `data_class="employee_personal"` when protecting explicitly typed scalars.
If a database already has employee data protected before this migration, re-protect
it through this pipeline before making employee datasets available.

Uploads now bind to the signed-in tenant, including preview digests and CSV IDs.
Canonical ingestion ignores any client-supplied tenant identity.

`protect_canonical_record` quarantines matched injection/bank-change requests.
Quarantined records cannot be enriched, retried for enrichment or retrieved as
ready evidence. Events store fixed reason codes, not source text or personal data.
The W1 filter is a deterministic pattern boundary; adversarial evaluation and
false-positive tuning remain Plan 7 work. It is not a proof that every injection
paraphrase is detected.

Plan 5 must call `authorize_tool` before each skill and commit the reservation before
dispatch. The method checks the manifest, side-effect class, persisted kill switch
and daily limits, and returns `agent:<tenant>:<agent>` for audit. Read/draft operations
are allowed; external/money operations are refused by this entry point. Their
approval/execution path belongs to Plan 5. Existing stub runs consult the stop state
before starting; their stream is still a synthetic trace.

## Configuration and rollout

Use `backend/.env.example` as the configuration reference:

- `SUPABASE_URL`, `SUPABASE_ANON_KEY` (legacy anon JWT API key),
  `SUPABASE_SERVICE_ROLE_KEY` (server-only invitation key).
- Keep the existing asymmetric JWT signing/JWKS configuration and access-token hook.
- Configure custom SMTP and code-based signup/magic-link/invite/recovery email
  templates using Supabase's `{{ .Token }}`. Default link templates do not fit this
  backend code-entry flow.
- `CORS_ORIGINS` is an exact app-origin allowlist. Cookie auth ignores the old regex
  origin option. Include the actual local port when developing.
- Set independent `TOKEN_ROOT_SECRET`, `TOKEN_HASH_SECRET`, and `VAULT_MASTER_KEY`.
  Secure-cookie auth refuses startup with placeholder/development production secrets.
- `AUTH_COOKIE_SECURE=true`, `AUTH_SESSION_HOURS=24`, `AUTH_STEP_UP_SECONDS=300`.
  `AUTH_COOKIE_SECURE=false` is only for local HTTP.
- `AUTH_ALLOW_BEARER=false` is the default. The old frontend's direct Supabase login
  must be replaced in Plan 8; the optional bearer escape hatch is for migration only.
- `AGENT_DAILY_TOOL_LIMIT=100`, `AGENT_DAILY_COST_LIMIT=10.0`. Cost units must be
  consistent across the Plan 5 dispatcher; these are server caps, not client claims.

Apply the new migration to PostgreSQL after all existing August migrations. The
SQLite startup path creates new tables and adds missing local membership/data-class
columns. Legacy privileged memberships receive their obvious job function; general
employees need an explicit Team assignment. No production migration was applied here.

Supabase references used for the provider implementation:

- [Auth REST specification](https://github.com/supabase/auth/blob/master/openapi.yaml)
- [TOTP lifecycle](https://supabase.com/docs/guides/auth/auth-mfa/totp)
- [Email OTP configuration](https://supabase.com/docs/guides/auth/auth-email-passwordless)

## Build evidence and remaining validation

Completed local static checks:

- Ruff lint across `backend/app`.
- Python compilation across `backend/app`.
- OpenAPI generation for 41 paths in the Plan 2 routers, saved to
  `docs/api/topic-e-plan-2-openapi.json`.
- Full backend imports and generates OpenAPI for 117 paths.
- ORM DDL compilation for all 42 models against SQLite and PostgreSQL dialects.
- PostgreSQL migration parsed with `pglast` (54 top-level statements); this checks syntax, not privileges,
  trigger behavior or a real Supabase rollout.

No test suite was added or run in this implementation pass. The old Plan 1 contract
test client deliberately injects `db=None` and sample principals, and several tests
assert stub datasets. It needs persistent database fixtures and AAL2 principals
before it can validate these live routes. Plan 2 is not marked as having passed the
old 372-test stub suite.

Still requires execution evidence before a release: authenticated provider signup,
email delivery, invitation/recovery, TOTP enrollment/step-up, refresh/revocation,
PostgreSQL RLS/trigger behavior, concurrency, tenant isolation, and adversarial
guardrail evaluation. Frontend integration and hosted publication are separate work.
