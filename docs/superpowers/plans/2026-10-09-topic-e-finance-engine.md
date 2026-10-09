# Plan 4 — Finance engine

**Implemented:** 2026-10-09. Forecast, scenarios, alerts and financing eligibility now run on a tenant's own imported records. Tenants with no imported bank balance still see the synthetic demo company, labelled `data_mode: "stub"`.

**Depends on:** Plan 3's business tables. Until those are merged, every tenant gets the demo company, and the live-data tests skip.

## What changed

| Piece | File | What it does |
|---|---|---|
| Engine | `backend/app/services/cashflow_engine.py` | Pure functions over a `CashBasis`: best/likely/worst bands, first shortfall, alerts, scenario shifts, per-agent totals. The arithmetic moved here unchanged from the stub. |
| Tenant basis | `backend/app/services/cash_basis.py` | Builds signals from Plan 3 records. Returns `None` when the tables are missing or the tenant has no bank balance. |
| Basis choice | `backend/app/services/cashflow.py` | Picks the live basis, or falls back to the demo company. |
| Financing profile | `backend/app/services/financing_profile.py` | Computes the facts the eligibility rules read, from the tenant's records. |
| Stubs | `backend/app/stubs/cashflow.py`, `backend/app/stubs/financing.py` | Hold only the demo company's data. Rules now take a `Profile`. |
| Routes | `backend/app/routes/cashflow.py`, `backend/app/routes/financing.py` | Forecast, scenarios, signals, matches and application packs use the person's tenant. |
| Agent runs | `backend/app/services/agent_runtime.py` | Same basis and profile as the pages. |

The API contract is unchanged. Only `data_mode` and the values differ.

## How records become cash signals

| Record | Becomes |
|---|---|
| Latest bank balance on or before the as-of date | Opening balance |
| Open payable | Outflow on its due date |
| Open purchase order | Outflow on its expected payment date, with source currency and rate. It is not also counted as a payable. |
| Approved or draft payroll run | Outflow on its pay date: gross pay plus employer contributions |
| Invoiced pipeline | Inflow on its expected payment date. Plan 3 already includes the collection delay in that date. The worst case adds 14 days (`WORST_CASE_EXTRA_DAYS`). |
| Pipeline with probability ≥ 0.5 | Inflow in the best and likely cases only |
| Pipeline with probability < 0.5 | Inflow in the best case only |
| Lost deal | Not counted |
| Expected marketplace payout | Inflow of the net amount; the worst case adds 7 days |
| Marketing spend not yet started | Outflow on its start date |
| Minimum balance | Read from tenant settings (`alerts.minimum_cash_balance`); RM50,000 if not set |

Stock reorders are not cash signals yet.

Signal labels never contain customer or supplier names. In these tables those names are vault tokens, so a label reads like "Invoice expected 08 Nov".

## Financing facts

Every fact below is computed from the tenant's records. A fact with no source is left out, and its rule fails with "not on record". No value is ever made up.

| Fact | Source |
|---|---|
| Projected shortfall gap | The 90-day forecast |
| Validated e-invoice share | E-invoice records |
| Receivables over 90 days | Invoiced pipeline more than 90 days past its expected payment date |
| Top customer share | Invoiced and ordered pipeline |
| Import payables share | Open payables and purchase orders, by currency |
| Annual revenue | The revenue the synthetic seed declares |

`months_trading` and `anchor_buyer_programme` have no source yet. Products that require them stay "not on record".

When nothing qualifies, the financing agent names the closest product and lists the rules it does not yet meet.

## Evidence

**`backend/tests/test_cash_basis.py`, always run:**
- Uncertain pipeline counts by probability.
- A missing fact fails its rule as "not on record".

**`backend/tests/test_cash_basis.py`, live tests (skip until Plan 3 merges):**
- Run against Plan 3's models in a scratch tree with the teammate's uncommitted files, and passed.
- On the importer's day-23 dataset, the forecast reconciles to:
  - opening balance RM116,400.00;
  - shortfall on day 23;
  - likely balance RM20,560.00;
  - gap RM29,440.00.
- The profile computes import share 0.52 and top customer share 0.31.
- The live agent run asks for the day-30 invoice before day 23, and that closes the gap.

**End to end on the importer itself:** `python -m seed.topic_e --as-of 2026-10-09` was run, then `seed.topic_e_original_fixtures`, then this engine, all on a scratch SQLite database.
- Forecast: the same day-23 shortfall, from 22 signals.
- Validated e-invoice share: 16%, because the seeded invoices are deliberately flawed for the readiness demo. Invoice financing is therefore not yet eligible.
- The agent run says so and names the rule to fix.

**Regression checks:** the existing cash-flow, financing, scorecard, positions and agent-run tests pass unchanged on the demo company.

## Not done

| Item | Status |
|---|---|
| Scorecard (`GET /financing/scorecard`) | Still uses the demo profile |
| Proposals saved to the inbox | Live-tenant agent proposals are shown in the run only; saving them to the review inbox is Plan 5 |
| Months trading, anchor-buyer programmes | Need a source, for example a company-profile field |
| Hosted run | Not run against hosted PostgreSQL; Plan 3's tables and migration are not deployed yet |
