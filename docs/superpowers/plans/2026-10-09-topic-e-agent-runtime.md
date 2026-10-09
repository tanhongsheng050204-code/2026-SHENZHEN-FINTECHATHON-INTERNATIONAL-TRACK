# Plan 5 — Agent runtime, persisted review inbox, earned autonomy, workspaces

**Implemented:** 2026-10-09, for companies whose data comes from their own imported records (Plan 4's "live" basis).

A company on the demo data still sees the sample inbox, sample agent cards and sample workspaces. Everything stays labelled as sample data, and the existing demo flows are unchanged.

## What a company on its own records now gets

| Piece | What it does | Where |
|---|---|---|
| Persisted review inbox | <ul><li>Each run's decidable proposals are saved, once: a repeated run reuses the open item instead of adding another.</li><li>Proposals are recorded as `agent_proposal_created` events and decisions as `review_decision` events on the company's audit chain. An item's status and approvals are replayed from those events.</li></ul> | `app/services/review_inbox.py` |
| Decision rules | <ul><li>**L1:** a holder of the reviewer position, or the owner.</li><li>**L2:** the owner.</li><li>**L3:** a maker who holds the position, then a different checker (the owner). Never edited.</li><li>**Compliance:** reads every item, decides none.</li><li>A decided item cannot be decided again.</li></ul> | same |
| Review record | <ul><li>Each agent's proposals, unedited approvals, approvals after an edit, and rejections are counted from people's decisions.</li><li>Promotion is recommended after at least 30 decided proposals with at least 90% approved unchanged.</li></ul> | `review_inbox.metrics` |
| Earned autonomy | <ul><li>A grant is an `autonomy_granted` event, so it persists and is audited.</li><li>A raise without a recommendation is refused.</li><li>L3 is never delegated.</li></ul> | `app/services/live_agents.py` |
| Agent cards | Plan 2's agent list (kill-switch state) when present, else the manifest list, with real metrics and grants laid over it | `app/routes/agents_live.py` |
| Position workspaces | <ul><li>Every skill with an engine behind it is computed from the company's records: forecast and shortfall alerts, collections to chase, financing matches, bills due in 30 days, committed purchase orders, next payroll, weighted pipeline, next marketplace payout.</li><li>Released skills without an engine say "Not computed from imported records yet" instead of showing a number.</li><li>The inbox count comes from the persisted inbox.</li></ul> | `live_agents.workspace` |

**Job functions.** They come from Plan 2's principal when it is present, otherwise from the demo team roster (`app/services/job_scope.py`). Stub calls receive job functions only if their signature takes them, so both the committed stubs and the teammate's Plan 2 versions work.

**Gates.** Decisions and autonomy changes use Plan 2's `require_step_up` when it exists.

**Routing.** These routes are registered before the stub routers. For a company on demo data they forward to the stubs.

## Evidence

**On `main`:**
- `tests/test_review_inbox_live.py`: 7 tests covering:
  - proposals saved once;
  - an L1 decision recorded, and a second decision refused;
  - Compliance read-only;
  - staff outside the position;
  - the L3 maker and checker order;
  - autonomy refused until 30 approvals, then granted and persisted;
  - computed workspaces (RM73,700.00 to collect, RM99,540.00 committed purchase orders flagged, payroll on the shortfall day flagged as risk).
- Evaluation tasks F21 and F22.
- Result: 30 tasks, 26 pass and 4 skip until Plans 2 and 3 merge.

**With the teammate's Plans 2 and 3 applied in a scratch copy:**
- The new tests, the agent-run and Passport tests and the harness all pass. The harness passes 30 of 30.
- The Plan 4 live-run test, which runs against the importer's data, now also checks that its two decidable proposals are saved and reused on a second run.

## Not done

| Item | Status |
|---|---|
| Inbox proposals from position skills other than cash, collections and financing | Only agent runs create proposals |
| Showing an approved proposal as acted on | Approval records the decision; nothing is sent or paid by design, and outbound sending stays with the existing outreach flow |
| Per-tenant promotion thresholds | Fixed at 30 and 90%; the tenant settings values (`approvals.promotion_min_sample`, `promotion_min_unedited_rate`) are not read yet |
| Daily briefing and the other planned (W2) skills | Not built |
