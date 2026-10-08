# FinBrain OS — Security Self-Assessment

2026 Shenzhen International FinTech Competition · International Track · Topic E: SME Finance Copilot
Draft of 2026-10-09. Every control below carries its real status; nothing is claimed beyond it.

## Status words

| Word | Meaning |
| --- | --- |
| **Built and tested** | In the repository and covered by automated tests that pass |
| **Built, verification pending** | Code exists; end-to-end verification against the real services is still to be done |
| **Contract and demo** | The API and screens exist and run on labelled synthetic data; the real service replaces them later |
| **Planned** | Designed, not built |

All data shown in the demonstration is synthetic and labelled as such.

---

## 1. What we protect

| Asset | Why it matters | Main protections |
| --- | --- | --- |
| Customer personal data (names, phones, emails, IC numbers, bank accounts) | PDPA 2010 (Malaysia); trust of the SME's customers | Detection and tokenization before any AI model sees it; encrypted vault; role-gated, audited disclosure |
| Company financial records (invoices, bank lines, payables, payroll) | Leaks harm the SME and its lenders | Per-tenant isolation with forced row-level security; tokenized amounts shown as bands |
| Employee data (payroll, leave) | Highest sensitivity inside the company | Separate token namespace; exact values need Owner/HR plus a recent authenticator check |
| Credentials and sessions | Account takeover is the shortest path to everything above | Password + emailed code + authenticator app; server-owned sessions; step-up for sensitive actions |
| Agent actions | An AI agent that sends or pays is a new attack surface | Autonomy ladder, review inbox, two-person rule for money, kill switch, guardrails |
| Audit evidence | Lenders and auditors must be able to trust it | Hash-chained, append-only logs anchored daily outside the database |

## 2. Identity and access

| Control | Status |
| --- | --- |
| Roles assigned only by the backend (`user_roles`), delivered in signed access tokens; the browser cannot choose or raise its role | Built and tested |
| Four roles (`general_employee`, `finance_ops`, `owner_director`, `compliance`) plus job functions per person (a person can hold several positions) | Built and tested |
| Backend-owned session (Plan 2): HttpOnly, Secure, SameSite=Lax cookie; CSRF token on every change; exact-origin allowlist; provider tokens never reach the browser | Built, verification pending |
| Sign-in with password **and** an emailed code on every sign-in | Built, verification pending |
| Authenticator app (TOTP, AAL2) mandatory for owner, finance and compliance | Built, verification pending |
| Step-up: sensitive actions (kill switch, autonomy grants, invitations, security settings) need an authenticator check from the last five minutes; the app asks for a code and retries | Backend built, verification pending · frontend built and exercised against a simulated backend |
| Idle timeout per company (5–60 minutes, can only be shortened); sign out everywhere; role changes invalidate old sessions | Built, verification pending |
| The last active owner cannot be removed or demoted | Built and tested (stub) · persistent version verification pending |

## 3. Data protection

| Control | Status |
| --- | --- |
| Personal data detection: deterministic patterns (Malaysian NRIC, phones, emails, bank accounts, RM amounts) plus an optional on-device NER model; detection failure falls back to patterns | Built and tested |
| Fail-closed gate: no external model call and no stored AI output may contain known personal data | Built and tested |
| Tokenization: values become per-tenant HMAC tokens; amounts become bands, so models never see exact figures | Built and tested |
| Token vault: three-tier key hierarchy (HKDF-SHA256, AES-256-GCM), context-bound ciphertext, resumable key rotation | Built and tested |
| Disclosure of an exact value: 30-second single-use grants bound to the request, every allow and deny audited; unauthorized roles see shaped masks | Built and tested |
| Database: row-level security enabled and forced on every table, public Data API grants revoked, audit tables reject updates and deletes | Built and tested |
| Employee data in its own token namespace and data class | Built, verification pending |
| Message templates refuse emails and phone, card or account numbers (including numbers written with spaces or dashes) and any brace that is not an approved placeholder | Built and tested |

## 4. AI agent safety

FinBrain gives every SME position an agent, so agent safety is designed in, not added on.

| Control | Status |
| --- | --- |
| **Autonomy ladder.** L0 watch · L1 drafts reviewed by the position holder · L2 external actions approved by the owner · L3 money movement needs a maker who holds the position, then the owner as a different checker; L3 drafts cannot be edited, so both approvers sign the same content | Contract and demo (rules built and tested; persistence in Plan 5) |
| Review inbox: nothing is sent or paid until a person approves; each item says whether the viewer may decide it; Compliance sees every item read-only | Contract and demo |
| Earned autonomy: an agent can be promoted only on its review record, one action at a time with an amount limit; L3 is never delegable | Contract and demo |
| Kill switch for one agent or all agents, persisted; runs check it before starting | Built, verification pending |
| Static skill allowlist per agent; daily tool-call and cost budgets enforced on the server | Built, verification pending |
| Guardrails: instruction-like text in emails, PDFs and messages (English, Malay, Chinese; Unicode-normalised) is quarantined before any model reads it; supplier bank-account changes are quarantined for callback and two approvers | Built, verification pending (deterministic patterns; adversarial evaluation is Plan 7) |
| Agents never execute payments or bank transfers; money actions end in the inbox | Built (by design: no payment integration exists) |

### OWASP Top 10 for Agentic Applications (2026)

| Risk | FinBrain control | Status |
| --- | --- | --- |
| ASI01 Agent goal hijack | Untrusted text treated as data; injection patterns quarantined before enrichment | Built, verification pending |
| ASI02 Tool misuse and exploitation | Per-agent skill allowlist; side-effect classes; external/money skills refused at the tool entry point | Built, verification pending |
| ASI03 Identity and privilege abuse | Agents run under per-tenant agent identities; tokenized data; role-gated disclosure | Built and tested (disclosure) · pending (agent identities) |
| ASI04 Agentic supply chain | Pinned dependencies (`uv.lock`, `package-lock.json`); no third-party scripts or fonts loaded at runtime | Built |
| ASI05 Unexpected code execution | No agent can run code or shell commands; no such tool exists | Built (by design) |
| ASI06 Memory and context poisoning | Quarantined records cannot become evidence; answers cite their sources | Built, verification pending |
| ASI07 Insecure inter-agent communication | Supervisor and agents run inside one backend process; no agent-to-agent network channel | Built (by design) |
| ASI08 Cascading failures | Daily budgets, kill switch, every external effect behind a person | Built, verification pending |
| ASI09 Human–agent trust exploitation | Evidence on every proposal; two-person rule for money; callback rule for bank changes | Contract and demo |
| ASI10 Rogue agents | Kill switch, autonomy only from review history, full audit of every proposal and decision | Built, verification pending |

## 5. Audit and evidence

| Control | Status |
| --- | --- |
| Two hash-chained, append-only audit logs (disclosure and workflow) | Built and tested |
| Daily anchoring of chain heads to a public Git repository (tamper evidence outside the database) | Built |
| Financing Readiness Passport: SHA-256 over canonical JSON; anyone can verify a received Passport; a document with fields that were never issued is rejected | Contract and demo (verification rules built and tested) |
| Audit packs for external auditors with a digest per item | Contract and demo |

## 6. Sharing with lenders and auditors

| Control | Status |
| --- | --- |
| Owner-only sharing for 1–30 days; ranges by default, exact values only by choice; revocable at any time | Contract and demo |
| Public share pages show only the shared document and verify it; no sign-in or other data reachable | Built (frontend) |
| Expiry enforcement and constant-time token checks on the server | Planned (Plan 6) |
| Emailed code for lenders before viewing | Planned (Wave 2) |

## 7. Company settings and safety floors

Owners can shape FinBrain to the company, but not below these floors: critical cash alerts always on and always sent to the owner; authenticator app mandatory for privileged roles; idle timeout at most 60 minutes. Security changes wait for a **different** Compliance user; rollback creates a new version and cannot loosen security.
Status: rules built and tested in the contract; database constraints built, verification pending.

## 8. Regulatory alignment

| Area | How FinBrain supports it |
| --- | --- |
| PDPA 2010 (Malaysia) | Data minimisation through tokenization; access and erasure workflows for data subjects; purpose-bound disclosure with audit |
| LHDN MyInvois e-invoicing | Readiness checks and validated e-invoice share used in the Passport |
| China cross-border trade (RMB) | Supplier payables in CNY shown with conversion; China financing catalogue; no browser dependency on services blocked in mainland China |

FinBrain is not certified under any standard, and we do not claim partnerships with banks or regulators. Financing products are real categories with illustrative terms, not offers.

## 9. Known limitations (residual risk)

- Plan 2 identity and session controls have passed static checks only; end-to-end tests against real Supabase (email delivery, TOTP, refresh, revocation, RLS triggers) are outstanding.
- Agent runs compute over the synthetic company's cash data, and their proposals point at existing review-inbox items rather than creating new ones; the review inbox and Passport issuance still run on synthetic stub data. Persistence comes in Plans 5 and 6.
- Guardrails are deterministic patterns; they will miss paraphrased injections until adversarial evaluation (Plan 7) tunes them.
- Share-link expiry is not yet enforced by the server.
- The backend is currently reached through a temporary tunnel; production needs a fixed HTTPS hostname under the app's parent domain.

## 10. Evidence

- Backend contract tests: 387 passing at commit `569e7bf` (FastAPI TestClient; role, rule and safety-floor cases).
- API contract: `docs/api/topic-e-contract.json` (54 operations), with a test that fails if it drifts from the code.
- Frontend: TypeScript build and lint pass on every commit; sign-in, step-up and every Topic E page exercised in a browser against simulated responses.
- Audit-chain anchors: `audit-anchors/` (daily workflow `anchor-audit-chain.yml`).
