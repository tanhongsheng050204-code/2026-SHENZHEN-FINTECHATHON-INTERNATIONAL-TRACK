# Agent registry

One card per agent. The cards are generated from the agent manifests in `backend/app/stubs/agents.py` on 2026-10-09.

The layout follows the AI-system inventory practice in the NIST AI RMF (Map and Govern functions) and ISO/IEC 42001. It is aligned with those frameworks, not certified.

## Rules that apply to every agent

- **Owner.** The company owner. They grant autonomy one action at a time, and can stop any agent or all of them.
- **Data.** Only the tenant's own records, through the same role checks as a person. Exact amounts follow the requesting person's role.
- **Side effects.** Every released skill only reads or drafts. External actions (L2) and money movement (L3) go through the review inbox. L3 needs a maker and a different checker and is never delegated.
- **Limits.** A tool call is refused unless the agent is built, the skill is released, and the side effect is read or draft. Plan 2 adds daily tool-call and cost budgets and persistent kill switches.
- **Evaluation.** `backend/eval/tasks.json` (see the Evaluated by column) and `backend/tests/test_agent_runtime.py`.

**"Runs today"** means the skill is executed by a real agent run (`app/services/agent_runtime.py`). The other released skills are declared in the manifest and shown on the agent cards. Their position workspaces still use sample data until Plan 5.

## Agents

| Agent | Works for | Autonomy | Released skills (side effect) | Runs today | Planned skills | Evaluated by |
|---|---|---|---|---|---|---|
| Supervisor | all positions | L0 | route_goal (read), stream_progress (read) | route_goal, stream_progress | daily_briefing | F11–F14 |
| Cash-flow | owner | L1 | forecast, shortfall_alerts, scenarios (read) | forecast | runway_and_fx, owner_briefing | F01–F03, F20 |
| Financing | owner | L1 | match_products (read); application_pack, readiness_passport (draft) | match_products | qualification_coaching | F06, F07 |
| Receivables | finance | L1 | rank_overdue (read), draft_reminders (draft), payment_promises (read) | rank_overdue | dispute_flags | F04, F05 |
| Operations | operations | L1 | cash_conversion_cycle, stale_approvals (read) | — | kpi_report, bottlenecks | — |
| Payables | finance | L1 | bill_calendar, bank_change_check (read) | — | early_payment_discounts, duplicate_bills, bank_reconciliation, sst_preparation | ADV-08 (Plan 2 guardrail) |
| Sales | sales | L1 | pipeline_inflows, credit_check (read) | — | quote_followups, win_loss, concentration_watch | — |
| Customer service | customer_service | L1 | triage_messages (read), suggest_replies (draft), dispute_risk (read) | — | knowledge_answers, response_times | — |
| Marketing | marketing | L1 | return_per_ringgit, payout_timing (read) | — | promo_cash_impact, segment_insights, content_drafts | — |
| Purchasing | procurement | L1 | committed_outflows, supplier_comparison (read) | — | landed_cost, three_way_match, reorder_suggestions | — |
| Inventory | logistics | L1 | reorder_alerts, cash_in_stock (read) | — | slow_stock, count_variance, shipment_tracking | — |
| HR and payroll | hr | L1 | payroll_cash_plan (read), statutory_reminders (draft) | — | leave_claims_checks, on_offboarding, headcount_forecast | — |
| Compliance | compliance | L1 | einvoice_readiness, ai_oversight (read), access_review (draft) | — | statutory_calendar, pdpa_assistant, retention_checks | — |
| Production | production | L0 (designed, not built) | — | — | production_plan, material_requirements, wip_cash, downtime_quality_log | — |

## Earned autonomy

Promotion to L2 for one action needs a recommendation from the review record. F10 checks that a promotion is refused without one and allowed with one.

Every agent's proposal metrics shown today are sample figures. Plan 5 records real ones.
