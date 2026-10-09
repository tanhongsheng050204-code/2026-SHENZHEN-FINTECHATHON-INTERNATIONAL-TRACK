# Known risks

Risks we have found and not yet removed, each with its current treatment. Dated 2026-10-09.

| # | Risk | Treatment |
|---|---|---|
| 1 | `einvoice_records.supplier_name` and `buyer_name` are stored in clear. They are business names, but a sole proprietor's business name can be a person's name. | **Accepted for the demo.** E-invoices legally carry these names, and every tenant query is scoped. Tokenizing them is a follow-up. |
| 2 | The disclosure path restores email and phone tokens for `general_employee`. Exact amounts are banded. | **Open decision.** Mask contact details for that role, or document why staff need them. |
| 3 | Guardrail patterns are deterministic, so a paraphrased injection may pass. | Tools are allowlisted independently (ADV-03), and ingested text cannot create actions (ADV-06). |
| 4 | Plan 2 (identity) and Plan 3 (importers) have no automated tests of their own, and break 82 existing tests in a scratch merge. | Must be fixed before they are committed. The evaluation harness passes 28/28 on that merge. |
| 5 | The public Passport verify and share endpoints have not been run against hosted PostgreSQL RLS. | Validate on Supabase before the demo. |
| 6 | The public endpoints have no rate limit. | Add one at the proxy or API. |
| 7 | Passport anchors are reported only where `audit-anchors/` is deployed with the API. | Set `AUDIT_ANCHOR_DIR` in production, or show anchors from the repository. |
| 8 | Promotion thresholds are fixed at 30 decisions and a 90% unedited-approval rate. | Read the tenant's settings values instead. A company on demo data still shows sample metrics. |
