# DuitDuit — Execution Evidence

Updated 2026-10-11 after the one-click demo company and ZAP scans; earlier: 2026-10-10 after the playbooks, voice input, assistant security evaluation and demo-script rewrite. Historical
figures below describe the earlier contract pass. The assistant evidence is below;
Plan 2/3 evidence is recorded in `docs/REMAINING_WORK.md` and
`docs/deployment/plan-2-3-review.md`.

## One-click demo company and ZAP scans: Oct 11 local verification

**Open the demo company** signs in to the synthetic company through the real password and
authenticator steps, run by the API with secrets only it holds (`app/auth/demo.py`).
`tests/test_demo_sign_in.py` covers it with a mocked identity provider:
- the RFC 6238 code vectors;
- the feature is off without all three secrets;
- origin checks;
- an account outside the demo company is refused;
- only the demo session can read the code;
- global sign-out, new authenticators and team changes are refused;
- briefings, alerts, email outreach and (in `tests/test_telegram_sender.py`) Telegram reminders from the demo company are never sent;
- the provisioning script writes secrets only to a new file.

In a browser, the real route ran against a local backend with a faked provider. It opened Today with the Demo authenticator showing a live code.

OWASP ZAP (`ghcr.io/zaproxy/zaproxy:stable`) scanned two targets locally: the production build served with the `vercel.json` headers, and the API offline. After the header fixes that the first run asked for, the results were:
- frontend baseline: **0 failures, 3 warnings, 64 passed**;
- API scan: **0 failures, 3 warnings, 117 passed**.

Reports are in `evidence/zap-2026-10-11/`. CI job `dast` repeats both scans.

| Check | Command | Result actually run |
| --- | --- | --- |
| Full backend suite (SQLite) | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **625 passed, 5 skipped** |
| Offline evaluation | `backend/`: `python -m eval.run <output dir>` | **42 passed, 0 failed, 0 skipped** |
| Frontend | `npx tsc -b`, `npm run build`, `npm run lint`, hardening check | Passed; 0 errors, 14 existing warnings |
| Hosted demo sign-in against real Supabase | — | **Not measured**: needs the production steps in `docs/deployment/production-checklist.md` |

## Phone layout and accessibility: Oct 11 local verification

All 18 signed-in screens were measured at 375 × 812 in Chromium:
- **Sideways scrolling:** before, 13 of them scrolled sideways. After, none do.
- **Touch targets:** tabs, chips, buttons and text toggles are at least 44 px tall.
- **Accessibility:** axe-core (WCAG 2.1 AA) finds 0 violations on 20 pages in both themes. Lighthouse accessibility scores 100 on eight app screens. Details are in [accessibility.md](accessibility.md).

## Financial analysis: Oct 10 local verification

`GET /analysis` and the Financial analysis tab give a cash-basis monthly profit and
loss, an expense breakdown, six ratios with formulas and sources, and the three
largest month-on-month changes. `tests/test_financial_analysis.py` checks every
figure by hand against the seed's July–September history. On a local copy of the
demo tenant (re-seeded with the same scripts) the tab shows September revenue
RM249,400.00, gross margin 49.5%, net RM39,200.00; bank matching is 9 of 10 lines and
the scorecard 605 (grade C). Migration `202610100003` widens the PostgreSQL stage
check for received sales; the disposable PostgreSQL run caught that it was needed.

| Check | Command | Result actually run |
| --- | --- | --- |
| Full backend suite (SQLite) | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **605 passed, 5 skipped** |
| Offline evaluation | `backend/`: `python -m eval.run <output dir>` | **42 passed, 0 failed, 0 skipped** |
| PostgreSQL RLS tests | the three PostgreSQL test files against a disposable pgvector/pg17 container, then `scripts.check_supabase` | **4 passed**; check passed |
| Frontend | `npx tsc -b`, `npm run build`, `npm run lint`, hardening check | Passed; 0 errors, 14 existing warnings |

## Attack tests ADV-10 to ADV-15: Oct 10 local verification

Six adversarial tasks were added to the offline evaluation. Each was confirmed to fail
against a deliberately broken variant (step-up accepting any past MFA, CSV risk
detection removed, the same-person rule removed, contact policy widened, refused links
not recorded) before passing on the real code. ADV-10 and ADV-11 also added a product
change: a link naming a real grant with a wrong signature or path is now recorded as a
guardrail event for that company, by the worker role scoped to it.

| Check | Command | Result actually run |
| --- | --- | --- |
| Offline evaluation | `backend/`: `python -m eval.run <output dir>` | **42 passed, 0 failed, 0 skipped** |
| Full backend suite (SQLite) | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **596 passed, 5 skipped** |
| PostgreSQL RLS tests | the three PostgreSQL test files against a disposable pgvector/pg17 container | **4 passed**, including the refused-link record under RLS |

## Alerts, eligibility steps and security checks: Oct 10 local verification

Alert rules now fire from imported records (`tests/test_alerts.py`); financing
matches name their next step (`tests/test_financing_path.py`); public share views
run under row-level security scoped to the link's tenant, rate limits are shared
in the database, and Trust & audit runs live checks.

| Check | Command | Result actually run |
| --- | --- | --- |
| Backend lint | `backend/`: `python -m ruff check .` | All checks passed |
| Full backend suite (SQLite) | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **595 passed, 5 skipped** (the 3 new skips are the PostgreSQL-only tests) |
| PostgreSQL RLS tests | `FINBRAIN_REVIEW_POSTGRES_URL=<disposable pgvector/pg17> pytest tests/test_plan23_postgres.py tests/test_passports_postgres.py tests/test_rate_limit_shared.py` | **4 passed**, after `scripts.check_plan23_migrations` applied every migration and `scripts.check_supabase` passed |
| Offline evaluation | `backend/`: `python -m eval.run <output dir>` | **36 passed, 0 failed, 0 skipped** |
| Frontend typecheck, build, lint, hardening | `frontend/` | Passed; 0 errors, 14 existing warnings; hardening passed |

The hosted Supabase project has not been re-tested in this pass.

## Consistency, privacy and bank matching: Oct 10 local verification

Commits after the playbooks: one company across cash, customers, financing and
playbooks; masked customer contacts for general employees (known risk 2); and
bank-line matching for the last completed month, which feeds the scorecard and
the month-end checklist. Checked against a local SQLite copy of the deployed
synthetic tenant seeded with the same scripts: month-end reports "September
2026: 4 of 5 bank lines match a record" with the RM1,250.00 transfer listed, and
the scorecard is 580 (grade C) with bank matching at 80%.

| Check | Command | Result actually run |
| --- | --- | --- |
| Backend lint | `backend/`: `python -m ruff check .` | All checks passed |
| Full backend suite | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **580 passed, 2 skipped** |
| Offline evaluation | `backend/`: `python -m eval.run <output dir>` | **36 passed, 0 failed, 0 skipped** |
| Frontend typecheck, build, lint | `frontend/`: `npx tsc -b`, `npm run build`, `npm run lint` | Passed; 0 errors, 14 existing warnings |
| Web hardening | `frontend/`: `node scripts/check-web-hardening.mjs` | Passed |

Hosted PostgreSQL, the production seed re-run and a browser recording are **not
measured** in this pass.

## A day with DuitDuit script: Oct 10 local verification

Section 4's deliverable is the rewritten `docs/submission/demo-script.md`.
It contains seven scenes with actions, narration, roles and shots to hold, using
a planned 0:00–5:00 timeline and 482 words of primary narration. The timing table
allocates 300 seconds; spoken duration and a timed browser rehearsal are **not
measured**. The source was checked for proposal vs grant issuance, L2 Owner
approval, the rolling cash window, missing month-end records and Compliance-only
audit access. This is a documentation pass; no production code or test was added.

| Check | Command | Result actually run before the documentation commit |
| --- | --- | --- |
| Backend lint | `backend/`: `python -m ruff check .` | All checks passed |
| Full backend suite | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **565 passed, 2 skipped** |
| Offline evaluation | `backend/`: `python -m eval.run ../output/demo-script-evaluation` | **36 passed, 0 failed, 0 skipped** |
| Frontend typecheck | `frontend/`: `npx tsc -b` | Passed |
| Frontend build | `frontend/`: `npm run build` | Passed |
| Frontend lint | `frontend/`: `npm run lint` | 0 errors, 14 existing warnings |
| Web hardening | `frontend/`: `node scripts/check-web-hardening.mjs` | Passed |
| Microphone policy regressions | `frontend/`: `node --test scripts/permissions-policy.test.mjs` | **8 passed** |

The backend process used an explicit local SQLite URL, disabled briefing pushes
and mocked/disabled providers. The two skips remain the legacy pre-Plan-3 case
and optional disposable PostgreSQL integration test. No audio, Telegram message,
email or lender link was sent by this writing/verification pass. Local PostgreSQL
checks were not rerun. Evaluation reports use a separate output folder to preserve
historical reports.

Section 3 commit `86dfe03` was pushed with approval, and all four jobs in
[CI run 37964538027](https://github.com/tanhongsheng050204-code/2026-SHENZHEN-FINTECHATHON-INTERNATIONAL-TRACK/actions/runs/37964538027)
passed, including the disposable PostgreSQL job. That CI covers section 3;
section 4's results above are local.

All four requested handoff sections now have local deliverables. Recording the
Telegram insert, real browser/provider rehearsal, timed rehearsal, MP4 export,
mirror reachability and production deployment are **not measured or completed**
by this script pass. Hosted authentication remains a separate verification item.
The script includes clearly labelled Telegram illustration and typed-voice
fallbacks, and distinguishes requests/proposals from explicit review decisions.

## Assistant security evaluation: Oct 10 local verification

Section 3 of `docs/handoff/2026-10-10-assistant-remaining-work.md` is implemented.
The original 30 evaluation tasks are retained and six `A-*` tasks are added.
These are local automated results with injected identities and mocked/disabled
providers, not evidence of hosted login or production authorization.

| Check | Command | Result actually run |
| --- | --- | --- |
| Backend lint | `backend/`: `python -m ruff check .` | All checks passed |
| Full backend suite | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **565 passed, 2 skipped** |
| Focused assistant security and harness tests | `backend/`: `python -m pytest tests/test_assistant_security.py tests/test_eval_harness.py -p no:cacheprovider -W ignore` | **28 passed**: 26 new security tests plus 2 harness tests |
| Offline evaluation | `backend/`: `python -m eval.run ../output/assistant-security-evaluation` | **36 passed, 0 failed, 0 skipped**: original 30 plus all 6 new tasks |
| Frontend typecheck | `frontend/`: `npx tsc -b` | Passed |
| Frontend build | `frontend/`: `npm run build` | Passed |
| Frontend lint | `frontend/`: `npm run lint` | 0 errors, 14 existing warnings |
| Web hardening | `frontend/`: `node scripts/check-web-hardening.mjs` | Passed |
| Microphone policy regressions | `frontend/`: `node --test scripts/permissions-policy.test.mjs` | **8 passed** |

The new tasks are `A-trick-typed`, `A-trick-spoken`, `A-role-limits`, `A-no-confirm`,
`A-provider-outage` and `A-no-words-in-audit`. They exercise real HTTP routes and
persisted synthetic L1/L3 proposals in two disposable SQLite tenants. The tests
compare replayed statuses, approvals and drafts before and after interpretation;
they require real proposal ids in confirmation plans, refuse employee/sales and
Compliance requests, check direct route denial, exercise the mocked provider
timeout, and verify private audit canaries are absent on a valid workflow chain.

Additional regressions check hostile model picks, invalid picks and provider
exception privacy, and verify that a plan does not bypass the decision endpoint's
recent-MFA and distinct maker/checker requirements. Deliberate faults are detected:
an actual decision during interpretation, a false step-up flag and typed words in
audit payloads even when the chain hashes are valid. No production source change
was needed for these tested safeguards.

The test process used an explicit local SQLite URL. The two skips remain the
legacy pre-Plan-3 case and the optional disposable PostgreSQL integration test.
PostgreSQL was not rerun locally for this section. No real audio or model/provider
request was sent. Acoustic quality, browser microphone capture, hosted sessions,
production tenant isolation and provider retention are **not measured**. Raw voice
audio reaches the transcription provider before the returned text is protected.
These scripted cases do not prove coverage of every possible injection.

Section 2 commit `51b5dfa` was pushed with approval, and all four jobs in
[CI run 37963433980](https://github.com/tanhongsheng050204-code/2026-SHENZHEN-FINTECHATHON-INTERNATIONAL-TRACK/actions/runs/37963433980)
passed. That CI run covers section 2; the section 3 results above are local.
At the end of this security pass, section 4 was open; the script pass above
subsequently completed the rewrite. Evaluation output was written to a
separate folder to preserve historical committed reports.

## Assistant voice: Oct 10 local verification

Section 2 of `docs/handoff/2026-10-10-assistant-remaining-work.md` is implemented.
Recording produces a protected transcript for review in the input box; it does
not submit a command. Only the person's Send action invokes the existing front door.

| Check | Command | Result actually run |
| --- | --- | --- |
| Backend lint | `backend/`: `python -m ruff check .` | All checks passed |
| Full backend suite | `backend/`: `python -m pytest -p no:cacheprovider -W ignore` | **539 passed, 2 skipped** |
| Voice regression tests | `backend/`: `python -m pytest tests/test_assistant_voice.py -p no:cacheprovider -W ignore` | **33 passed** |
| Existing offline evaluation | `backend/`: `python -m eval.run ../output/voice-evaluation` | **30 passed, 0 failed, 0 skipped**; separate output folder preserves the earlier committed report |
| Frontend typecheck | `frontend/`: `npx tsc -b` | Passed |
| Frontend build | `frontend/`: `npm run build` | Passed |
| Frontend lint | `frontend/`: `npm run lint` | 0 errors, 14 existing warnings |
| Web hardening | `frontend/`: `node scripts/check-web-hardening.mjs` | Passed |
| Microphone policy regressions | `frontend/`: `node --test scripts/permissions-policy.test.mjs` | **8 passed** |

The voice tests use synthetic WebM-signature bytes and a mocked provider; these
are HTTP and SDK contract checks, not audible clips. They cover size and duration
limits, content types, unavailable/malformed provider responses, authentication,
user-based quotas, real existing PII protection, no disk spooling or persistent
storage, private audit payloads on a valid hash chain, and spoken requests using
the same refusal and confirmation path as typed requests. No real audio was sent
to a provider during verification. Voice audio, transcripts and generated tokens
are not persisted. Audio goes inline through the existing Gemini client.

The browser caps capture at 30 seconds and 2,000,000 bytes; the server bounds the
upload and validates the declared duration without decoding actual WebM timing.
The ten-per-minute quota is per authenticated tenant/user **per server process**.
The microphone is hidden when the provider is unconfigured or the browser cannot
record WebM/Opus. Permission policy allows this origin only.

The test runtime used an explicit local SQLite URL. The two skips remain the
legacy pre-Plan-3 test and the optional disposable PostgreSQL integration test.
Local PostgreSQL checks were not rerun for this voice pass. A temporary SDK test
environment was repaired outside the repository, retaining the locked Pydantic
2.13.4 version; no dependency lock or contract snapshot was changed.

Microphone capture, acoustic transcription quality, hosted authentication and
production deployment are **not measured**. These results cover local code only.
At the end of this voice pass, sections 3–4 remained open. The security evaluation
above subsequently completed section 3; the demo-script rewrite remains open.

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

At the end of this playbook pass, sections 2–4 remained open; the voice pass above
subsequently completed section 2. Interactive browser, hosted authentication,
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
| Evaluation harness | Historical Plan 2/3 pass: 30 tasks (22 functional, 8 adversarial). The Oct 10 assistant pass extends this to **36 tasks** (22 functional, 14 adversarial), all passing offline; see the section above. The complete demo command writes a fresh report in its evidence directory. |
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
