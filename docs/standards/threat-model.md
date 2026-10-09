# Threat model (STRIDE)

## Scope

Browser → Vercel (static app and same-origin `/api` proxy) → FastAPI on Cloud Run → Supabase PostgreSQL. Telegram and email come in as extra inputs.

## Assets

- Tenant business records.
- Personal data: customer contacts and salaries.
- The token vault and its keys.
- The two audit hash chains.
- Issued Passports and audit packs.
- Session cookies.
- External share links.

## Trust boundaries

| # | Boundary |
|---|---|
| 1 | Browser ↔ API |
| 2 | API ↔ database |
| 3 | Inbound Telegram and email ↔ ingestion |
| 4 | API ↔ optional model provider |
| 5 | Public share links ↔ tenant data |
| 6 | CI ↔ repository (audit anchors) |

## Threats and controls

| STRIDE | Threat | Boundary | Control | Evidence |
|---|---|---|---|---|
| Spoofing | Someone uses another person's session | 1 | HttpOnly cookie sessions with a CSRF header; recent TOTP step-up before sharing and money decisions (Plan 2) | Plan 2 doc; F15 with Plan 2 |
| Spoofing | A forged or guessed share link | 5 | Links are `grant_id` plus an HMAC over grant and tenant, checked in constant time; forged → 404 | `test_expired_and_forged_links_are_refused` |
| Spoofing | A fake Passport shown to a lender | 5 | Public verification against the audit chain; changed fields are named only for the holder of the issued digest | F07, `test_verification_is_not_an_oracle…` |
| Tampering | Edits to audit history | 2 | Hash-chained, append-only chains, verified per tenant; daily tail anchors committed to git by a separate credential | F16, `tests/test_audit_anchor.py` |
| Tampering | Changes to a Passport after issue | 5 | SHA-256 of canonical JSON recorded on the chain; the stored document is re-hashed on verification | F07 |
| Tampering | Instructions hidden in ingested content | 3 | Content guardrail quarantine (Plan 2); ingested text cannot create actions; tools allowlisted | ADV-01, ADV-02, ADV-06 |
| Repudiation | "I never shared that" / "I never looked" | 5 | Grant creation, revocation and every external view are chain events | `test_lender_link_works_until_revoked…` |
| Repudiation | An approval nobody admits to | 1 | Approvals carry approver IDs; L3 records both the maker and the checker | F15 |
| Information disclosure | An employee reads exact amounts or salaries | 1 | Role-based detokenization; amounts banded; payroll lines encrypted in an employee namespace (Plan 3) | ADV-04 |
| Information disclosure | Cross-tenant reads | 2 | Tenant filter in every query plus PostgreSQL RLS; agent runs bound to tenant and person | F17, `test_run_cannot_be_read_by_another_tenant` |
| Information disclosure | Verification used as an oracle on Passport contents | 5 | Field names and the recorded hash are returned only to the holder of the issued digest | `test_verification_is_not_an_oracle…` |
| Information disclosure | Personal data sent to a model provider | 4 | Protected text only; planner preflight refuses payloads that still contain known personal data | `conversation_planning.plan_conversation` |
| Information disclosure | Secrets committed to git | 6 | `gitleaks` scan of the full history in CI | CI supply-chain job |
| Denial of service | Provider outage or slowness | 4 | Timeouts and a deterministic fallback | ADV-07 |
| Denial of service | Oversized or malicious uploads | 1, 3 | Size, type and signature checks before parsing; CSV limits (Plan 3) | ADV-05 |
| Elevation of privilege | An agent acting beyond its manifest | 1 | `authorize` checks agent, skill and side effect on every call; kill switch and budgets (Plan 2) | ADV-03 |
| Elevation of privilege | Autonomy granted without a record | 1 | Promotion needs a recommendation; L3 is never delegable | F10 |

## Not yet covered

- Hosted RLS for the public verify and share endpoints, which read the chain before a tenant context exists. Needs validation on Supabase.
- A rate limit on the public verify and share endpoints.
- Email one-time codes for lenders.
