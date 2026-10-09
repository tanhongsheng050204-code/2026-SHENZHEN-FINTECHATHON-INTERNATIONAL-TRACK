# FinBrain OS completion ledger

Updated 2026-10-09 after inspecting the current source and Claude's latest remote
commits. This records executable work and remaining prerequisites. It does not
mark the entire Six Documents scope complete.

## Completed in this continuation

| Gap | Result | Evidence |
| --- | --- | --- |
| Eight CSV schemas existed only in the backend | Data sources now supports bank, payables, purchase orders, stock, payroll, marketing, marketplace payouts and sales pipeline; preview, validation issues, duplicate handling, explicit commit and recent history | `frontend/src/components/BusinessCsvImportCard.tsx`; backend import regression tests |
| Mapping UI exposed two schemas and omitted FX | All eight types and their complete fields are generated from the backend contract, including `fx_rate`; mapping matching uses the selected type | `scripts.export_import_ui`; snapshot drift test |
| Staff with optional MFA could not complete their first protected action | The step-up prompt now offers authenticator enrollment, QR/setup key and verification; cancellation/unmount resolves pending requests without retrying the action | `frontend/src/components/StepUpPrompt.tsx`; build/typecheck passed, hosted provider and interactive browser checks pending |
| Daily agent budget charges could disappear at request rollback | Each tool reservation is committed before invoking the tool, including read-only runs and Supervisor startup | `test_agent_budget_reservation_survives_request_rollback` |
| Autonomy promotion ignored tenant settings | Recommendations now use the current tenant sample and rate thresholds; the exact rate is compared before display rounding | `test_promotion_uses_tenant_threshold_and_exact_rate` |
| One-command demo left original pages in the default tenant | The demo command now seeds both sets of screens into the same synthetic tenant and exports its CSVs; provider keys are disabled; failed evaluations stop the command | Executed `scripts.demo_kit`; 30/30 evaluation tasks passed |
| Deployment checker did not know Plan 2/3 tables | Checks new tables/columns, forced RLS, browser privileges, session-secret restrictions and enabled safety triggers; accepts schema-qualified pgvector types | Executed `scripts.check_supabase` against disposable PostgreSQL; added to the PostgreSQL CI job |
| Handover still said Plans 2/3 were uncommitted and evaluation was absent | Main status, submission evidence and security assessment updated | This ledger and linked review evidence |

## Current execution evidence

- Full backend suite with the optional PostgreSQL integration enabled:
  **450 passed, 1 skipped**. The skip is a legacy pre-Plan-3 test.
- Frontend lint: zero errors, 14 existing warnings. TypeScript/Vite build passes.
- Complete synthetic demo: eight import batches, 53 source rows, original page
  fixtures in the same tenant, all 30 offline evaluation tasks passed.
- Deployment schema checker passes on PostgreSQL 17 with all 34 migrations.
- Earlier committed review CI passed all four jobs at `3a20339`:
  https://github.com/tanhongsheng050204-code/2026-SHENZHEN-FINTECHATHON-INTERNATIONAL-TRACK/actions/runs/37878885099
- The new CSV and MFA interface is compiled but has not yet been exercised in a
  browser against hosted Supabase. Backend HTTP/service and database coverage
  must not be presented as that browser evidence.

## Plans 1–9 status

| Plan | Current state | Remaining |
| --- | --- | --- |
| 1 — Contract | Original snapshot frozen; current contract drift tested | Keep current snapshots synchronized when adding routes |
| 2 — Identity/security | Committed backend and frontend flows, persistent team/settings, regression coverage, database checks | Hosted OTP/TOTP/invitation/recovery/session rehearsal; configure custom SMTP |
| 3 — Imports/demo data | Eight persistent importers and frontend workflow; complete synthetic demo | Hosted import/permission rehearsal with provisioned demo accounts |
| 4 — Finance engine | Forecast, scenarios and financing on tenant records | Hosted reconciliation; optional data facts absent from source remain absent |
| 5 — Agent runtime/inbox | Cash, collections and financing runs; persisted decisions and autonomy; tenant thresholds and durable budgets | Remaining job-specific executable skills, daily briefing, and the W2 skill list |
| 6 — Passport/grants | Issuance, packs, verification, expiry/revocation and consented links | Production audit anchors; hosted public-link/RLS/stream rehearsal |
| 7 — Evaluation/standards | 30 offline tasks, dependency audits, secret scans and standards pack | Broader adversarial cases, provider-outage/hosted rehearsal; no certification claimed |
| 8 — Frontend | Auth, Team, settings, cash, inbox, positions, Passport and complete CSV workflow | Browser/accessibility/mobile rehearsal; hosted end-to-end flow |
| 9 — Web/China | Security headers, bundled fonts, public-link rate limits and reachability notes | Custom domain/provider account; actual mainland-China measurements and mirror |

## Tasks that need external access or a human deliverable

1. **Cloud Run and Supabase deployment:** connect the intended accounts and identify
   the project/service. Apply migrations, deploy the backend, and verify its API
   through the same-origin proxy. The connected Vercel account only exposes the
   preview project and cannot access `finbrainos.vercel.app`.
2. **Hosted authentication:** configure SMTP and code-based email templates,
   provision authorized demo accounts, and perform real OTP, authenticator,
   recovery, invitation and revocation checks.
3. **Audit anchors:** configure the production database secret and execute the
   anchor workflow; local test chains are not production anchoring evidence.
4. **China access:** connect a custom domain/hosting account and gather actual
   mainland measurements. Do not infer reachability from local CI.
5. **Submission:** record the demo video, arrange its mirror, collect screenshots
   and complete the organizer's submission requirements.

## Further implementation available in the repository

The original Six Documents also plans additional position agents and W2 skills:
operations briefing, sales/credit controls, customer-service replies and disputes,
marketing return analysis, procurement comparisons and landed costs, inventory
reorder/slow-stock work, HR/statutory preparation and compliance preparation.
Some workspaces compute values already; that does not mean every listed skill has
an executable tool and review proposal. Production/manufacturing remains designed
unless explicitly implemented. These are separate feature work beyond the core
integration gaps completed above.

## Reproduce the complete local demo

From `backend/`, choose a new database path:

```powershell
uv run python -m scripts.demo_kit ../output/my-demo.db --report-dir ../output/my-demo-evidence
```

The command refuses an existing database, disables external model calls, exports
synthetic CSVs and reports the exact local settings to serve that file. Use those
settings together: the fictional vault keys are not production credentials. No
login or membership is created automatically.
