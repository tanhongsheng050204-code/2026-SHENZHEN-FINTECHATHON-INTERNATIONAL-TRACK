# DuitDuit — Execution Evidence

Updated 2026-10-10 after building the four assistant playbooks. Historical
figures below describe the earlier contract pass; current evidence is recorded in
`docs/REMAINING_WORK.md` and `docs/deployment/plan-2-3-review.md`.

## Assistant playbooks: Oct 10 local verification

Section 1 of `docs/handoff/2026-10-10-assistant-remaining-work.md` is implemented.
These are local automated results, not hosted deployment or browser evidence.

| Check | Command | Result actually run |
| --- | --- | --- |
| Backend lint | `backend/`: `python -m ruff check .` | All checks passed |
| Full backend suite | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **506 passed, 2 skipped** |
| Playbook regression tests | `backend/`: `python -m pytest tests/test_playbooks.py -p no:cacheprovider -W ignore` | **36 passed** |
| Existing offline evaluation | `backend/`: `python -m eval.run ../output/playbook-evaluation` | **30 passed, 0 failed, 0 skipped**; separate output folder preserves the earlier committed report |
| Frontend typecheck | `frontend/`: `npx tsc -b` | Passed |
| Frontend build | `frontend/`: `npm run build` | Passed |
| Frontend lint | `frontend/`: `npm run lint` | 0 errors, 14 existing warnings |
| Web hardening | `frontend/`: `node scripts/check-web-hardening.mjs` | Passed |

The two backend skips are the legacy pre-Plan-3 test (the tables now exist) and the
optional integration test requiring a disposable migrated PostgreSQL database.
PostgreSQL and hosted Supabase verification were not rerun for this playbook pass.
The test process used an explicit local SQLite URL, not the production database.

The new tests cover all four playbooks, phrase routing before generic goals,
sales refusal, compliance's read-only boundary, lender and reminder L2 proposals,
one open reminder per customer, tenant isolation, no sendable outreach or active
grants, kill switches, recent-MFA decisions, missing financing facts, accurate cash
minimum arithmetic, and id-only playbook events on a valid workflow hash chain.
Synthetic forecast checks retain day 23, RM20,560.00 likely balance and RM29,440.00
gap. Bank reconciliation is always explicitly **not measured**.

Approving a bank-sharing proposal records the decision; the owner then uses the
existing Passport controls to select a recipient and expiry and issue the link.
Reminder delivery is likewise not implemented by the playbook. No external action
is performed by interpreting or building either playbook.

Sections 2–4 of the handoff remain open. Interactive browser, hosted authentication,
production deployment and real external delivery are **not measured** here.

## Automated checks

| Check | Command (from the folder shown) | Result |
| --- | --- | --- |
| Backend test suite | `backend/`: `uv run pytest -q` | Earlier contract pass: **394 passed**; Plan 2/3 review: **447 passed, 1 skipped** with PostgreSQL enabled. See the completion ledger for the latest run. |
| Topic E contract tests | `backend/`: `uv run pytest -q tests/test_contract_*.py` | **132 passed** |
| Backend lint | `backend/`: `uv run ruff check .` | All checks passed |
| API contract drift | included in the suite (`test_committed_contract_matches_the_code`) | Current code matches `docs/api/topic-e-current-contract.json`; the original `topic-e-contract.json` remains frozen and its operations are preserved |
| Frontend type-check and build | `frontend/`: `npm ci && npm run build` | Built with no errors |
| Frontend lint | `frontend/`: `npx eslint .` | 0 errors (14 pre-existing warnings) |
| Same-origin API proxy | local test against a fake backend (method, body, cookies, CSRF, streaming, refused paths) | All assertions passed |

CI (`.github/workflows/ci.yml`) runs the backend lint and tests and the frontend type-check, lint and build on every push.

## What the tests cover (Topic E contract)

| Area | Examples of behaviour pinned by tests |
| --- | --- |
| Roles and positions | One person can hold several positions; staff decide only their own positions' items |
| Review inbox | L2 needs the owner; L3 needs a maker who holds the position and a different checker; L3 drafts cannot be edited; Compliance sees all items read-only; each item says whether the viewer may decide |
| Cash flow | Shortfall on day 23 of the demo company; scenarios move events; risk signals never move the balance |
| Financing | Ineligible products name the failing rule; the scorecard scores 695 (grade B) from published bands; points follow the bands at their edges |
| Passport | Documents with fields that were never issued are rejected; verification recomputes the SHA-256 |
| Settings | Safety floors (owner alerts, MFA for privileged roles, 60-minute idle cap); security changes and security rollbacks wait for Compliance; equivalent submissions are not changes |
| Templates and imports | Unknown or malformed placeholders and personal numbers refused; import mappings match on every header regardless of order, case and byte-order mark |
| Agent runs | The Supervisor routes English, Malay and Chinese goals; each agent calls the real forecast, late-receivables scenario and financing rule engine, and every message is built from their results; off-topic goals get an honest refusal; every tool call is checked against the agent manifest; run ids are HMAC-bound to tenant and person, so tampered or foreign ids return 404 (`tests/test_agent_runtime.py`) |
| Finance engine on tenant data | Forecast, scenarios and financing rules run on a tenant's imported records; on the synthetic importer's data the forecast reconciles to the documented day-23 shortfall (RM20,560.00 likely balance, RM29,440.00 gap); facts with no source fail their rule as "not on record" instead of using a made-up value (`tests/test_cash_basis.py`; the live-data tests run once Plan 3 is merged) |
| Passport, audit packs and share links | Issued onto the tenant's audit chain; verification names a changed field only for the holder of the issued digest; expired and revoked links return 410, forged ones 404; every external view is a chain event (`tests/test_passports_live.py`) |
| Persisted review inbox and earned autonomy | Agent-run proposals saved once to the review inbox on the audit chain; L1/L2/L3 decision rules with maker and checker; review records counted from decisions; promotion refused until 30 approvals, then persisted (`tests/test_review_inbox_live.py`) |
| Evaluation harness | 30 tasks as data (`backend/eval/tasks.json`): 22 functional, 8 adversarial mapped to OWASP agentic risks; all 30 pass after the Plan 2/3 merge. The complete demo command writes a fresh report in its evidence directory. |
| Supply chain | `pip-audit` found 76 known vulnerabilities in 5 Python packages and `npm audit` 1 high; all fixed by upgrading, and CI now runs both audits, a full-history `gitleaks` scan and an SPDX SBOM on every push |

## Live demonstrations

| What | Where |
| --- | --- |
| Preview of every Topic E screen with synthetic data (signed in as a demo owner) | https://finbrain-topic-e-preview.vercel.app |
| Public lender view of a shared Passport, with verification | https://finbrain-topic-e-preview.vercel.app/lender/passports/demo-grant-token |
| API contract (OpenAPI) | `docs/api/topic-e-contract.json` |

## Not yet evidenced

Stated plainly so nothing is over-claimed:

- **Hosted Plan 2 authentication:** the committed backend, frontend and mocked-provider regression tests exist; real Supabase email delivery, TOTP and recovery still need hosted verification.
- **Audit-chain anchors**: the daily `anchor-audit-chain.yml` workflow exists, but no `audit-anchors/` files are in the repository yet; it needs the `PRODUCTION_DATABASE_URL` secret to run.
- **External audit evidence:** local and CI PostgreSQL checks pass, but they do not establish production deployment or an independent security certification.
- **Production deployment** on Cloud Run behind the same-origin proxy: documented in `docs/deployment/cloud-run-and-vercel.md`, not yet performed.

## Before submission

- [ ] Re-run the commands above on the final commit and update this page.
- [ ] Add screenshots of the CI run and the demo flow.
- [ ] Add the audit-anchor evidence once the workflow has run.
- [ ] Link the demo video and its mainland-China mirror.
