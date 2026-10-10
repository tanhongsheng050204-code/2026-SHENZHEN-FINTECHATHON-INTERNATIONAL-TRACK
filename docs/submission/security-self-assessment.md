# DuitDuit — Security Self-Assessment

2026 Shenzhen International FinTech Competition · International Track · Topic E: SME Finance Copilot
Draft updated 2026-10-10 for assistant security evaluation. Every control below carries its real status; nothing is claimed beyond it.

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
| Customer personal data (names, phones, emails, IC numbers, bank accounts) | PDPA 2010 (Malaysia); trust of the SME's customers | Text detection and tokenization before AI enrichment; encrypted vault; role-gated, audited disclosure. Voice audio goes to Gemini for transcription before the returned text is protected. |
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
| Fail-closed text gate: text interpretation skips the model when known personal data remains; stored AI text is protected. Voice transcription sends audio first, then protects the returned text. | Built and tested locally; real voice/provider rehearsal pending |
| Text tokenization: values become per-tenant HMAC tokens and amounts become bands before AI enrichment. Voice audio may contain exact spoken values before transcription. | Built and tested |
| Token vault: three-tier key hierarchy (HKDF-SHA256, AES-256-GCM), context-bound ciphertext, resumable key rotation | Built and tested |
| Disclosure of an exact value: 30-second single-use grants bound to the request, every allow and deny audited; unauthorized roles see shaped masks | Built and tested |
| Database: row-level security enabled and forced on every table, public Data API grants revoked, audit tables reject updates and deletes | Built and tested |
| Employee data in its own token namespace and data class | Built, verification pending |
| Message templates refuse emails and phone, card or account numbers (including numbers written with spaces or dashes) and any brace that is not an approved placeholder | Built and tested |

## 4. AI agent safety

DuitDuit gives every SME position an agent, so agent safety is designed in, not added on.

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

| Risk | DuitDuit control | Status |
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

### Assistant front door: security evaluation added Oct 10

The following tasks are registered in `backend/eval/tasks.json`, with checkers in
`backend/eval/checks.py` and regressions in `tests/test_assistant_security.py`.
They use real HTTP routes, injected authenticated identities, mocked/disabled
providers and disposable SQLite databases containing persisted synthetic proposals.

| Task | Control verified offline |
| --- | --- |
| `A-trick-typed` | Employee injection refused; finance's L3 payment plan still requires confirmation and step-up; no foreign-tenant proposal or decision |
| `A-trick-spoken` | Mocked transcription previews the words without acting; submitted transcript has the same role, confirmation and step-up result as typed text |
| `A-role-limits` | Employee restricted pages and goals refused; direct Team, workflow-audit and agent-run routes denied; sales bank playbook denied; Compliance cannot decide |
| `A-no-confirm` | Interpretation alone leaves persisted statuses, approvals and drafts unchanged in both tenants and appends only command audit events |
| `A-provider-outage` | An exercised model timeout falls back to an answer; recognized rules bypass the provider; no 500 or proposal change |
| `A-no-words-in-audit` | All six command kinds emit fixed audit metadata and ids only; typed words and private canaries are absent; tenant workflow chain verifies |
| `ADV-10` | A link forged from company B's valid link with A's grant id is refused (404) and recorded for A; B cannot list or revoke A's grants |
| `ADV-11` | A share link with a changed signature, or a lender link used on the auditor path, is refused (404) and recorded; the real link still opens |
| `ADV-12` | An authenticator check older than the 5-minute step-up window cannot approve a money item; a fresh one can |
| `ADV-13` | Instructions hidden in an imported CSV cell block the import before any row is stored; a guardrail event is recorded; nothing is proposed or sent |
| `ADV-14` | On a persisted L3 money item, the maker's second approval is refused (409 same_person_cannot_approve_twice) |
| `ADV-15` | A general employee sees a customer's email and phone masked, even from vault rows written under the older, wider policy; finance sees them |

Additional tests check hostile/invalid model picks, private provider exceptions,
recent-MFA enforcement and distinct L3 maker/checker approvals. Injected faults
verify that the evaluation detects state changes without confirmation, missing
step-up flags and words recorded on an otherwise valid hash chain.

**Status: built and locally tested.** See `execution-evidence.md` for counts from
the actual run. Scripted injection cases do not prove coverage of all paraphrases
or production authorization. Identities are injected in these tests; hosted login,
sessions and PostgreSQL policies require their separate verification.

Voice sends raw audio to Gemini for transcription. Personal data in speech is not
redacted before that provider call; the returned text is protected before it is
shown. The voice path does not persist audio, transcripts or its generated tokens.
Real acoustic quality, browser capture and provider retention behavior are **not
measured** here. Offline tests send no real audio and make no provider call.

## 5. Audit and evidence

| Control | Status |
| --- | --- |
| Two hash-chained, append-only audit logs (disclosure and workflow) | Built and tested |
| Daily anchoring of chain heads to a public Git repository (tamper evidence outside the database) | Built |
| Financing Readiness Passport: computed from the company's records, SHA-256 over canonical JSON recorded on the tenant's workflow chain; public verification names every changed field, re-verifies the whole chain and reports the covering anchor; a document with fields that were never issued is rejected | Built and tested |
| Audit packs for external auditors: a digest per item, the pack hash recorded on the audit chain, payroll as run totals only | Built and tested |

## 6. Sharing with lenders and auditors

| Control | Status |
| --- | --- |
| Owner-only sharing for 1–30 days; Passport values are ranges; revocable at any time; creating, revoking and every view are audit-chain events; the grantee email is stored only as a token | Built and tested |
| Public share pages show only the shared document and verify it; no sign-in or other data reachable | Built (frontend) |
| Expiry and revocation enforced on every view (410), HMAC-signed links checked in constant time, forged links refused (404) | Built and tested |
| Emailed code for lenders before viewing | Planned (Wave 2) |

### Web hardening and China reachability

| Control | Status |
| --- | --- |
| Content Security Policy (scripts only from the app itself, no inline script, `frame-ancestors 'none'`, `object-src 'none'`), HSTS, `nosniff`, Referrer-Policy, Permissions-Policy, `X-Frame-Options: DENY` | Built; verified on a Vercel deployment by browsing 9 pages with no violations |
| `noindex` on app and shared pages; `robots.txt` and a sitemap listing only the landing, security and legal pages; a title per page; `/.well-known/security.txt` (RFC 9116) pointing at `SECURITY.md` | Built |
| No browser request to a third-party origin: bundled fonts, QR codes drawn locally (invoice UINs no longer go to an online QR service), API through the same-origin proxy | Built; checked in CI by `frontend/scripts/check-web-hardening.mjs` |
| App served from a domain that loads in mainland China | Not done: the app is still on `vercel.app`, which GreatFire reports as mostly blocked. See `docs/deployment/china-reachability.md`. |

## 7. Company settings and safety floors

Owners can shape DuitDuit to the company, but not below these floors: critical cash alerts always on and always sent to the owner; authenticator app mandatory for privileged roles; idle timeout at most 60 minutes. Security changes wait for a **different** Compliance user; rollback creates a new version and cannot loosen security.
Status: rules built and tested in the contract; database constraints built, verification pending.

## 8. Regulatory alignment

| Area | How DuitDuit supports it |
| --- | --- |
| PDPA 2010 (Malaysia) | Data minimisation through tokenization; access and erasure workflows for data subjects; purpose-bound disclosure with audit |
| LHDN MyInvois e-invoicing | Readiness checks and validated e-invoice share used in the Passport |
| China cross-border trade (RMB) | Supplier payables in CNY shown with conversion; China financing catalogue; no browser dependency on services blocked in mainland China |

DuitDuit is not certified under any standard, and we do not claim partnerships with banks or regulators. Financing products are real categories with illustrative terms, not offers.

## 9. Known limitations (residual risk)

- Plan 2 identity and session controls have mocked-provider regression coverage and disposable PostgreSQL permission/trigger checks. End-to-end tests against hosted Supabase (real email delivery, TOTP, refresh and revocation) remain outstanding.
- A company on its own records gets a persisted review inbox, real review records and persisted autonomy grants, all on its audit chain. A company on the demo data still sees sample inbox items and sample agent metrics, labelled as such.
- Guardrails are deterministic patterns. The offline adversarial evaluation passes its scripted cases; this does not prove coverage of paraphrased or novel injections.
- Passport anchors appear only where the anchor files are deployed with the backend; the public verification endpoint has not been validated against hosted PostgreSQL row-level security.
- The backend is currently reached through a temporary tunnel; production needs a fixed HTTPS hostname under the app's parent domain.

## 10. Evidence

- Assistant security: the six `A-*` tasks above and `tests/test_assistant_security.py`; current local suite and evaluation counts are in `execution-evidence.md`.
- Backend contract tests: 387 passing at commit `569e7bf` (FastAPI TestClient; role, rule and safety-floor cases).
- API contract: `docs/api/topic-e-contract.json` (54 operations), with a test that fails if it drifts from the code.
- Frontend: TypeScript build and lint pass on every commit; sign-in, step-up and every Topic E page exercised in a browser against simulated responses.
- Audit-chain anchors: `audit-anchors/` (daily workflow `anchor-audit-chain.yml`).
