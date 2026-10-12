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
| 7 | An AI tool (MCP client) with a company key ↔ API |

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
| Denial of service | Hammering or guessing on the public verify and share endpoints | 5 | 30 requests a minute per client address, then 429 | `test_public_endpoints_are_rate_limited` |
| Denial of service | Oversized or malicious uploads | 1, 3 | Size, type and signature checks before parsing; CSV limits (Plan 3) | ADV-05 |
| Elevation of privilege | An agent acting beyond its manifest | 1 | `authorize` checks agent, skill and side effect on every call; kill switch and budgets (Plan 2) | ADV-03 |
| Elevation of privilege | Autonomy granted without a record | 1 | Promotion needs a recommendation; L3 is never delegable | F10 |
| Spoofing | A leaked AI connection key used by someone else | 7 | Keys are read-only, expire (90 days by default), name the tools they may call, work only while their owner is still an owner, and are revocable; the owner sees when each was last used and for what; per-address and per-key rate limits | ADV-16, `tests/test_mcp.py` |
| Elevation of privilege | An AI key reaching a tool it was not given | 7 | The key's tool list is checked on `tools/list` and on every `tools/call`, before the tool runs or is recorded | ADV-17 |
| Elevation of privilege | A non-owner minting a key that reads as the owner | 1 | Creating, listing and revoking keys need the owner role and a recent authenticator check | ADV-18 |
| Spoofing | A sign-in from a stolen password and code on a new device | 1 | Each sign-in is recorded; a device is known by a random id in an HttpOnly cookie, not by browser string or address (both forgeable); a device the person has not used before appears as a warning in the owner's and Compliance's security feed, and ordinary sign-ins cannot push security events out of it | `tests/test_security_activity.py` |
| Information disclosure | The sign-in record itself identifying a person's location | 1 | Only browser family, system and an HMAC fingerprint are kept; no IP address or browser string | ADV-21 |
| Tampering | One company pausing the collection of another's invoice | 1, 2 | A hold is accepted only for a receivable on the company's own board or one of its own customers | ADV-19 |
| Repudiation | "We never knew about the breach" | 1 | The incident register records who opened it and who completed each step, on the chain; closing waits for the required steps | `tests/test_incidents.py` |

## Not yet covered

- Hosted RLS for the public verify and share endpoints, which read the chain before a tenant context exists. Needs validation on Supabase.
- A rate limit shared across server instances (today each instance limits on its own).
- Email one-time codes for lenders.
- New-device sign-ins are shown in the app's security feed but not emailed.
- AI connection keys are bearer keys; OAuth for remote MCP servers is not built.
