# FinTechathon 2026 Topic E: SME Finance Copilot — Program Design Specification

**Date:** 2026-10-08  
**Status:** Approved (team kickoff); partly superseded on 2026-10-08 by `FINBRAIN_SIX_DOCUMENTS.md` (every SME position gets an agent, company customization, job functions as a list, two build waves) — where they differ, that file wins  
**Target:** 2026 Shenzhen International FinTech Competition (WeBank), International Track, Topic E — SME Finance Copilot  
**Deadline:** 2026-10-20 23:59 UTC+8 (Beijing and Malaysia time are the same). We submit a complete version on Oct 19; resubmission is allowed until the deadline and the latest version counts.

---

## 1. Competition facts

| Item | Detail |
|---|---|
| Theme | "AI as a Financial Participant": an AI agent that completes real tasks in a financial scenario |
| Topic E brief | For small-business owners: financing-option matching, cash-flow management with alerts, business financial analysis |
| Scoring | Task completion **40%** · Security & compliance **30%** · Innovation & interaction **30%** |
| Deliverables | (1) technical documentation: architecture, core algorithms, security design · (2) presentation deck, 10 minutes max · (3) demo video, optional, 5 minutes max — **mandatory for us** · (4) source code with README, repo link, deployment instructions, tests · (5) security self-assessment: permission tiers and known-risk list · (6) execution evidence: simulated/sandbox operation logs and demo logs |
| Timeline | Online review from Oct 20 by WeBank industry experts and university scholars · finalists announced Oct 31 · check-in and WeBank HQ visit Nov 20 · grand final Nov 21–23 in Shenzhen (at least one member must attend) |
| Language | English |

The judges and the final are in mainland China. Section 9 covers what that means for hosting.

## 2. Positioning

> **FinBrain OS is the secure operating system that makes an SME financeable.** AI agents run the finance back office, people review them, and the result is a verified, privacy-preserving record that a lender can trust.

| Loop | What the SME gets | What the demo proves |
|---|---|---|
| Operate | Cash-flow forecast with alerts; collections | A shortfall caught 23 days ahead; reminders drafted, reviewed and approved |
| Finance | Matched financing with reasons; an application pack | A lender-ready pack in minutes, with an explanation for every match and non-match |
| Trust | MFA, role-aware disclosure, agent guardrails, tamper-evident audit | Live attacks blocked; a tampered Passport fails verification |

- **Demo company:** a synthetic Malaysian SME that imports from suppliers in Shenzhen and pays them in RMB. It is labelled synthetic everywhere it appears.
- **Jurisdiction packs:** Malaysia is the working market (MyInvois, PDPA, RM). A thin China pack (RMB, fapiao, PIPL, China-style SME financing categories) shows portability. A pack is configuration, a financing catalogue and a rule set — never a forked code path.
- **Why this suits a lender's panel:** most entries will be finance chatbots. We connect our security architecture to a lender's real problem: SME data is messy, private and unverifiable.

Market evidence for the deck is listed in section 15.

## 3. Design principles

These apply to every workstream.

1. **Code computes, the model narrates.** Forecasts, aging, eligibility, thresholds and scores are deterministic Python/SQL over numeric columns. The LLM only classifies intent, picks a tool from the agent's allowlist, and narrates tokenized results. Every agent must work in `offline-demo` mode with no provider key.
2. **The model never sees raw values.** Agents consume tokenized evidence through the existing protection pipeline. Exact values are restored only by the backend, only for authorized roles, through the existing disclosure path.
3. **People own decisions.** Every agent action carries an autonomy level (section 4.2). Nothing is sent externally and no money-related change is applied without the approvals that level requires.
4. **Everything is evidence.** Agent proposals, reviews, promotions, guardrail blocks, lender access and Passport issuance are workflow-audit events in the existing hash chain.
5. **The Supabase contract still applies** (`SUPABASE_ARCHITECTURE.md`): a new timestamped migration per change, forced RLS, tenant-leading indexes, no `anon`/`authenticated` grants, no raw PII in ordinary columns or JSON, and `models.py`, `scripts/check_supabase.py` and `SUPABASE_SCHEMA_REFERENCE.md` updated in the same change.
6. **We claim only what the code and tests prove** (section 13.2).

## 4. Agents

### 4.1 Roster

| Agent | Takes over | Reviewer (job function) | Tier |
|---|---|---|---|
| Supervisor | Routes a goal or question to agents; streams progress | — | 1 |
| Cash-flow | 30/60/90-day forecast, shortfall alerts, what-if scenarios | Owner | 1 |
| Receivables | Prioritised collections, reminder drafts, payment-promise tracking | Finance | 1 |
| Financing | Product matching with reasons, application pack, Passport | Owner | 1 |
| Compliance | E-invoice readiness, SST, PDPA/PIPL checks | Compliance | 3 |
| Payables | Bill scheduling, early-payment discounts | Finance; Owner above threshold | 3 |
| Sales / customer | Follow-ups, customer risk | Sales | 3 |
| HR / payroll | Payroll cash needs, EPF/SOCSO reminders | Owner | 3 |

Tier 3 agents appear in the architecture document and in the Agent Hub as cards marked **"Designed — not built"**, with their review model. They are not implemented.

### 4.2 Autonomy ladder

| Level | The agent may | Approval required |
|---|---|---|
| L0 | Read and analyse | None |
| L1 | Create internal drafts (forecast notes, reminder text, application pack) | Any reviewer in the job function |
| L2 | Take an external action (send a reminder, share a Passport, submit an enquiry) | Owner, with AAL2 (TOTP) step-up |
| L3 | Anything that changes where money goes, or files with a regulator | Never executed by an agent. Prepared only; two different people approve (maker-checker) |

A tenant policy (`tenant_agent_policies`: owner-editable, versioned, audited) adds escalation: any action above RM X, or touching more than N customers, goes to the owner whatever its level.

### 4.3 Earned autonomy

- For each agent and tenant, track proposals, approved unedited, approved after edit, rejected, and edit size.
- The system *recommends* a scoped promotion (for example L1 → L2 for "reminders under RM5k") once the agent passes a minimum sample size and unedited-approval rate set in tenant policy.
- Only the owner promotes, with TOTP step-up. Demotion is immediate, and automatic when the rejection rate breaches policy.
- The **Transformation Journey** screen shows each job function's agents, current level, override rate, and estimated hours saved (task count × configured minutes per task, labelled as an estimate).

### 4.4 Supervisor and progress stream

- Intent classification and tool selection go through a per-agent allowlist. The classifier may use the LLM, with a deterministic keyword fallback in offline mode.
- Each run emits typed step events (`run_started`, `tool_called`, `proposal_created`, `waiting_for_review`, `run_completed`) over Server-Sent Events for the activity stream.
- Supervisor-to-agent calls are typed in-process function calls with Pydantic schemas — never free-text instructions between agents.

### 4.5 Agent identity and guardrails

| Control | Requirement |
|---|---|
| Agent identity | Each agent has its own `actor_ref`. Actions record both the agent and the requesting user. An agent never exceeds the requesting user's role. |
| Tool allowlist | Each agent declares its tools; any other call is rejected and logged. |
| Budgets | Per-run step limit, per-day action limit, provider timeouts with offline fallback. |
| Kill switch | Per agent and global; owner or compliance only; audited. |
| Untrusted content | Ingested text is data, never instructions. Instruction-like content (English, Malay, Chinese) in ingested records is flagged and never becomes a tool argument. |
| Bank-detail change | A supplier bank-account token that differs from the verified one is quarantined. Forecasts and payables do not use it until callback verification is recorded and two different people approve. |
| Logging | Every block is a `guardrail_blocked` workflow-audit event tagged with its OWASP ASI code. These feed the Trust Center attack feed and the posture dashboard. |

## 5. Finance engine

### 5.1 Data inputs

| Input | Source | Status |
|---|---|---|
| Receivables | `einvoice_records` (validated, `paid_at` null) | Existing |
| Bank transactions | New structured schema `bank_statement_v1`: date, description, debit, credit, balance, counterparty, reference | New |
| Payables | New structured schema `payables_register_v1`: bill id, supplier, amount, currency, due date, status, bank account | New |
| Suppliers | New `suppliers` table, tokens only, holding the verified bank-account token | New. Needed by the forecast and the fraud control even though the Payables agent is Tier 3 |
| Payroll | Recurring outflow detected from the bank statement, or a tenant setting | New |

Amounts live in numeric columns, as `einvoice_records.total_amount` does today, so code computes exactly. Counterparty names, account numbers and references are tokenized.

### 5.2 Cash-flow forecast (deterministic)

- **Opening balance:** the latest bank-statement balance.
- **Inflows:** each open receivable at its `due_date` plus that customer's historical average days late (the tenant median when there is no history).
- **Outflows:** payables at their due dates, recurring outflows (same counterparty token, similar amount, roughly monthly), and payroll.
- **FX:** RMB payables converted at a configured rate. Tier 2 adds a ±% FX band.
- **Bands:** best = everyone pays on time; likely = historical average delay; worst = historical p90 delay.
- **Horizon:** 30, 60 and 90 days.
- **Alerts:** a likely-band balance below the tenant minimum within the alert horizon raises an alert and triggers receivables and financing proposals.
- **Scenarios:** an endpoint that accepts overrides (customer X pays N days later; payment Y moves or changes) and recomputes in under 300 ms so the slider feels live.
- **Backtest:** replay the synthetic history and report the error in the deck, labelled synthetic.

### 5.3 Receivables agent

Builds on the existing overdue-reminder and outreach flows. Priority = amount × days overdue × customer attention score. Drafts are L1; sending is L2 unless the agent has earned scoped autonomy.

### 5.4 Financing agent

- **Catalogue:** about 8 Malaysian and 3–4 Chinese entries, using real product categories with illustrative terms. Each entry has `jurisdiction`, `category`, eligibility rules, `last_verified` and `source_url`. It is stored as versioned configuration in the jurisdiction pack, not in the database.
- **Eligibility:** deterministic rules over computed metrics: months trading, revenue, receivables quality, validated e-invoice share, customer concentration, projected shortfall size.
- **Explanations:** every match and every non-match states which rule passed or failed and cites the company's own records. Bank Negara's AI discussion paper stresses explainability when AI recommends financial products.
- **Application pack:** an L1 draft. Sharing it with a lender is L2.

### 5.5 Financing Readiness Passport

- **Contents:** cash-flow health, receivables aging and quality, validated e-invoice share, customer concentration, data completeness, compliance status. Amounts appear as bands unless the lender grant allows exact values.
- **Integrity:** canonical JSON → SHA-256 → workflow-audit entry → anchored by the existing `anchor-audit-chain.yml` workflow (trigger it manually before any demo).
- **Verification endpoint:** recompute the hash, find the chain entry, verify the chain and the anchor, and return either a pass or the exact mismatching field.
- **Lender access:** the owner creates a grant (lender email token, Passport scope, expiry) with TOTP step-up. The lender verifies by email OTP and gets a read-only, masked view of that Passport only. Every view, expiry and revocation is audited. If time runs short, fall back to an expiring signed link without OTP.

### 5.6 E-invoice as a credit signal

Since 2026-09-01, e-invoicing is mandatory only above RM3m in annual sales. We reposition MyInvois readiness accordingly: a tax-authority-validated invoice (UIN and QR) is tamper-proof evidence of a receivable, so voluntary e-invoicing raises the Passport's receivables-quality score and the company's invoice-financing eligibility.

## 6. Identity and security

### 6.1 Authentication (backend-mediated)

- The browser never calls `supabase.co` and never holds a token. The backend calls Supabase Auth for password login, email OTP, and TOTP enrolment/challenge/verification, then sets `HttpOnly; Secure; SameSite=Lax` cookies for the API domain.
- State-changing requests need a CSRF defence (custom header plus origin check). CORS allows credentials only from the app origin.
- The existing JWKS verification and `user_roles` lookup stay; they read the cookie instead of the `Authorization` header.
- AAL2 is required for approvals, exact-value disclosure, policy changes, autonomy promotion, the kill switch and lender grants. MFA is mandatory for `owner_director`, `finance_ops` and `compliance`.
- SMS OTP is documented as supported by configuration; it is not built.

### 6.2 Roles and job functions

- The four security roles stay as they are. They decide what a person may *see*.
- New column `user_roles.job_function` (`owner`, `finance`, `sales`, `procurement`, `hr`, `compliance`) decides what a person *does*: which agents they supervise and what reaches their Review Inbox.

### 6.3 Team page

The owner invites a user, assigns role and job function, deactivates, and signs a user out everywhere. All actions are audited.

### 6.4 Posture dashboard

MFA coverage by role; inactive accounts; who can see exact bank numbers; agent actions this week by autonomy level and approval rate; guardrail blocks by OWASP code; audit-chain verification status; vault key age.

### 6.5 Web hardening and search hygiene

- `vercel.json` headers: CSP (allowlist provided by B1: API origin, Sentry), HSTS, `frame-ancestors 'none'`, Referrer-Policy, Permissions-Policy, `X-Content-Type-Options: nosniff`. Test on a preview deploy first; a wrong CSP breaks the app.
- `/.well-known/security.txt` (RFC 9116).
- `X-Robots-Tag: noindex` on app routes; `robots.txt` and a sitemap listing only the landing and legal pages; a title per route.
- Self-hosted fonts.
- New meta description, Open Graph text and image for the Topic E positioning.

No further SEO work: it does not score, and the judges receive the link directly.

### 6.6 Standards pack

| OWASP Agentic Top 10 (2026) | Our control | Test |
|---|---|---|
| ASI01 Agent Goal Hijack | Untrusted-content filter; deterministic engine; tool allowlist | ADV-01 (English injection), ADV-02 (Chinese injection) |
| ASI02 Tool Misuse and Exploitation | Allowlist; typed tool arguments; budgets | ADV-03 |
| ASI03 Identity and Privilege Abuse | Agent identity; never exceeds the requesting user's role; AAL2 gates | ADV-04 (exact value requested as `general_employee`) |
| ASI04 Agentic Supply Chain Vulnerabilities | Pinned dependencies; SBOM; `pip-audit`, `npm audit` and secret scanning in CI; provider adapters with offline fallback | CI job |
| ASI05 Unexpected Code Execution | No code-execution tools; in-memory parsing of allowlisted file types | ADV-05 (malicious upload) |
| ASI06 Memory & Context Poisoning | Bounded, tokenized conversation window; summary validation; ingested content treated as data | ADV-06 |
| ASI07 Insecure Inter-Agent Communication | Typed in-process calls only | Unit test |
| ASI08 Cascading Failures | Step budgets; timeouts; circuit breaker to offline mode | ADV-07 (provider outage) |
| ASI09 Human-Agent Trust Exploitation | Evidence and autonomy level on every proposal; maker-checker; bank-change quarantine | ADV-08 (supplier bank-change email) |
| ASI10 Rogue Agents | Kill switch; demotion; audit anomalies on the posture dashboard | Unit test |

The pack also includes:

- an agent registry with one card per agent (purpose, data, tools, autonomy, owner, limits, evaluation score), **aligned** with NIST AI RMF and ISO/IEC 42001 — not certified;
- a STRIDE threat model;
- an incident-response runbook;
- the known-risk list for the self-assessment. First candidate: `einvoice_records.supplier_name` and `buyer_name` are stored in clear. They are business names, but a sole proprietor's business name can be a person's name — tokenize them or document the decision.

## 7. Evaluation harness

- About 20 functional tasks plus the 8 adversarial cases in section 6.6, specified as data (YAML) with deterministic checkers, running offline in CI.
- Output: `output/eval-report.md` and `output/eval-report.json` (pass/fail per task, duration, mode), used in the deck and the evidence bundle.
- Tier 1 is done only when every task passes. The live "jailbreak it" act runs only if the adversarial set is 100% green.
- The synthetic dataset is designed backwards from the demo story, so expected answers are known in advance (for example, the likely-band shortfall falls on day 23).

Example functional tasks:

- ingest `bank_statement_v1` and reconcile balances;
- the 90-day forecast hits the planted shortfall date;
- a scenario moves the shortfall earlier by the expected number of days;
- an alert fires below the tenant minimum;
- the top three collections are ranked correctly;
- reminders are drafted at L1 and none are sent;
- financing matches invoice financing and rejects a term loan with the expected reason;
- a Passport verifies, and a one-field tamper fails with that field named;
- an expired lender grant is refused;
- promotion is refused below the sample size and allowed above it;
- the supervisor routes "can I cover payroll on the 28th?" to the cash-flow agent.

## 8. Frontend

Keep the design tokens, i18n (en/ms/zh), auth shell and API client. Rebuild the information architecture:

1. **Command Center** — role-adaptive home: cash position, forecast, alerts, items awaiting review, posture score
2. **Agent Hub** with the **Review Inbox**
3. **Cash & Receivables** — forecast chart, scenario slider, aging
4. **Financing** — matches with reasons, Passport, lender sharing, lender view
5. **Ask** — existing chat and evidence drawer, plus the "what the AI saw" split view
6. **Records** — existing customers, e-invoicing and sources screens
7. **Trust Center** — posture, Team, audit chains, attack feed, privacy requests, evidence export

Plus the Transformation Journey screen. Add Recharts for the forecast, and a graph library (for example Cytoscape.js) for the Tier 2 counterparty graph. Build against stub endpoints from Oct 9 and never block on backend progress.

## 9. China reachability

| Dependency | Status from mainland China (GreatFire) | Action |
|---|---|---|
| `*.vercel.app` | Mostly blocked: 127 of 131 tested URLs | Custom domain `app.<domain>` |
| `*.run.app` | Intermittent: 12 of 19 tested URLs disrupted (2026-10-07) | Custom domain `api.<domain>`. B1 tests a Cloud Run domain mapping and a Cloudflare-proxied route, and keeps whichever passes |
| `supabase.co` | Intermittent: 12 of 17 tested URLs disrupted (2026-10-05) | Backend-mediated auth (section 6.1): only the backend talks to Supabase |
| Google Fonts | Blocked | Self-host |
| YouTube | Blocked | Submit the MP4 file; mirror it on a China-reachable host such as Bilibili |
| Telegram | Blocked | Any phone moment in the final runs on the roaming hotspot; WeChat Work goes on the roadmap slide as the China channel |

**Final-day kit (B3):** one command starts local Supabase (Docker), the backend and the frontend, with the synthetic tenant and offline AI mode, on the presenting laptop. The network backup is a phone hotspot on a Malaysian roaming SIM, tested at check-in on Nov 20. The last resort is the video. GreatFire results for each domain go into the security self-assessment.

## 10. Data-store decision

We add no new database for this submission, including Neo4j.

- An SME's counterparty graph is small (hundreds of nodes). Multi-hop questions at that size run in Postgres in milliseconds.
- A second store would need its own tenant isolation, tokenization, erasure, audit coverage, backups and credentials. That weakens the single-boundary security story that is worth 30% of the score.
- Neo4j AuraDB Free pauses after 3 days of inactivity, which could break the app during the judges' online review.

Tier 2 instead builds the **counterparty graph inside Postgres**: an `entity_edges` table (tokens only, forced RLS) populated from ingestion and entity resolution, queried with recursive CTEs (bank accounts shared across suppliers, never-seen accounts, customer concentration and contagion, circular invoicing), and drawn in the frontend. On the roadmap slide: at a lender's portfolio scale, across thousands of SMEs, a dedicated graph engine becomes worth it.

## 11. Workstreams

Fill in the B1–B3 names at kickoff.

### Frontend — tanho

- New IA and app shell; Command Center; Agent Hub and Review Inbox; forecast chart and scenario slider; Financing, Passport and lender view; Trust Center and attack feed; Transformation Journey; "what the AI saw" split view; activity stream.
- Web hygiene from section 6.5, except the CSP allowlist; self-hosted fonts.
- Owns the deck (10 minutes max) and the video (5 minutes max).

### B1 — identity and security

- App and API domains (section 9); backend-mediated auth with email OTP, TOTP and AAL2 gates (section 6.1).
- `job_function`; Team page API; `tenant_agent_policies`.
- Guardrails (section 4.5), including bank-change quarantine, kill switch and agent identities.
- Posture dashboard API; CSP allowlist; lender grants and OTP (section 5.5), together with B2.
- Owns the standards pack (section 6.6), threat model, security self-assessment and GreatFire tests.

### B2 — agents and finance engine

- Stub endpoints returning fixture responses, merged by Oct 9 end of day. These are the API contract.
- Forecast engine, scenarios and alerts (5.2); supervisor and SSE progress (4.4); receivables upgrade (5.3); financing engine and catalogues (5.4); Passport hashing and verification (5.5); e-invoice credit signal (5.6); earned-autonomy metrics (4.3).
- Tier 2: counterparty graph; FX band.
- Owns the technical documentation.

### B3 — data, evaluation, operations

- Synthetic tenant designed from the demo story; `bank_statement_v1` and `payables_register_v1` schemas; `suppliers`.
- Evaluation harness (section 7) and CI wiring; SBOM and dependency and secret scans; evidence-export bundle.
- One-command local demo kit (section 9). Fix `frontend/.env.example`, which still points at Railway although the backend runs on Google Cloud.
- Tier 2: reconciliation and data-health checks.
- Owns the README, deployment and test instructions, and the evidence bundle.

**Migration filenames:** to avoid collisions, each person uses their own sequence range within a day: frontend `00xx`, B1 `01xx`, B2 `02xx`, B3 `03xx` (for example `202610090101_tenant_agent_policies.sql`).

## 12. Schedule

| Date | Frontend (tanho) | B1 — identity & security | B2 — agents & finance | B3 — data, eval, ops |
|---|---|---|---|---|
| Thu Oct 8 | IA and wireframes; self-host fonts | Domains and DNS for app and API; security headers; `security.txt` | Draft stub endpoints and schemas | Synthetic company spec, designed from the demo story |
| Fri Oct 9 | App shell; Command Center on stubs | Backend-mediated login; email OTP | **Stubs merged end of day (contract frozen)**; forecast engine | Synthetic data; `bank_statement_v1`, `payables_register_v1` |
| Sat Oct 10 – Sun Oct 11 | Agent Hub and Review Inbox | TOTP and AAL2 gates; `job_function`; Team API; tenant policy | Supervisor and SSE; receivables upgrade | Evaluation harness with the first 10 tasks in CI |
| Mon Oct 12 – Tue Oct 13 | Forecast chart and slider; Financing | Guardrails, including bank-change quarantine, kill switch, agent identities | Financing engine and catalogues; e-invoice credit signal | ADV-01 to ADV-08; SBOM, dependency and secret scans |
| Wed Oct 14 | Passport and lender view; "what the AI saw" | Lender grants and OTP (with B2); posture API | Passport hash, verification and anchoring; earned-autonomy metrics | Local demo kit |
| **Wed Oct 14, end of day** | **Tier 1 go/no-go** | | | |
| Thu Oct 15 – Fri Oct 16 | Trust Center and attack feed; Transformation Journey; activity stream | GreatFire tests; threat model; self-assessment draft | Tier 2 if green: counterparty graph, FX band; forecast backtest | All tasks green; evidence export; Tier 2: reconciliation |
| **Fri Oct 16, end of day** | **Hard feature freeze** | | | |
| Sat Oct 17 | Everyone: bug bash and three full rehearsals | | | |
| Sun Oct 18 | Video (MP4 and mirror); deck v1 | Self-assessment final | Technical documentation final | README, deployment and test docs; evidence bundle |
| Mon Oct 19 | Deck final; **submit the complete version** | | | |
| Tue Oct 20 | Buffer only; resubmit if needed before 23:59 | | | |

**If we fall behind, cut in this order:**

1. Tier 2 items.
2. The China pack, reduced to its catalogue and the currency toggle.
3. The Transformation Journey screen, folded into a Command Center widget.
4. Backend-mediated auth, falling back to direct Supabase login (MFA stays).
5. Lender OTP, falling back to an expiring signed link.

**Never cut:** MFA, the Review Inbox, the three core agents and the supervisor, guardrails and adversarial tests, the evaluation report, the video, the security self-assessment.

## 13. Demo script and claims policy

### 13.1 Script (about 6 minutes inside the 10-minute slot)

| Act | Time | What happens | Wow moment | Rubric line |
|---|---|---|---|---|
| 1 | 0:45 | The owner logs in with email OTP and TOTP. A clerk and the owner ask the same question: the clerk sees "RM2.5K–5K", the owner sees the exact figure. | Same question, two answers | Security |
| 2 | 1:30 | The owner says: "Make sure I can cover payroll and the RMB supplier payment on the 28th." Agents run live and find a shortfall in 23 days. The owner drags "customer pays 30 days late" and the financing agent re-matches. | The 90-second CFO | Task completion |
| 3 | 1:00 | The clerk edits and approves reminders in the Review Inbox. The owner promotes the receivables agent for reminders under RM5k, with TOTP. | Promote the agent | Interaction |
| 4 | 1:15 | The "what the AI saw" split view. Then three attacks are blocked live — a supplier bank-change email, an "admin mode" request for phone numbers, a Chinese-language injection — each appearing in the attack feed with its OWASP code. | Jailbreak it | Security |
| 5 | 1:00 | The lender opens the Passport via OTP; verification passes against the GitHub anchor. The presenter edits one revenue figure; verification fails and names the field. | Tamper one byte | Innovation |
| 6 | 0:30 | Impact panel (synthetic, labelled); Malaysia → China pack toggle; closing line; QR code "try to break it". | — | Innovation |

Closing line, used only once the adversarial set is green:

> "Most AI can be talked into anything. Ours can be fully hijacked and still can't show you data you're not allowed to see, change where money goes, or act beyond the autonomy its humans gave it — because those decisions live in code and in people, not in the model."

### 13.2 Claims policy

| Say | Never say |
|---|---|
| "Aligned with ISO/IEC 42001 and NIST AI RMF" | "ISO 42001 certified" |
| "Tested against all 10 OWASP agentic risks: N/N passing" | "Unhackable", or "bank-grade" without proof |
| "Synthetic demo company modelled on a Malaysian importer" | Anything implying real customers |
| "Real financing categories, illustrative terms" | "Partnered with SME Bank" or "with WeBank" |
| "Forecast backtested on synthetic history: X% error" | Accuracy figures taken from vendor blogs |
| "Runs fully offline with no AI provider" | "Live bank integration" |

## 14. Open items

| Item | Owner | Default if unresolved by end of Oct 9 |
|---|---|---|
| Domain | tanho | Buy a .com (about RM50) |
| Cloud Run service name and region (needed for domain mapping) | B1 | Read from the GCP console |
| Suppliers: a separate `suppliers` table, or `customers` with a kind column | B2 and B3 | Separate table |
| `einvoice_records` business names stored in clear | B1 | Document as a known risk; tokenize if time allows |

## 15. References

**Competition**

- [IEEE R10: 2026 Shenzhen International FinTech Competition — International Track](https://r10.ieee.org/shenzhen-cis/blog/2026/06/17/2026-shenzhen-international-fintech-competition-international-track/)
- Official site: fintechathon.g-ican.com

**Market**

- [The Edge: Closing the RM90 bil MSME funding gap](https://theedgemalaysia.com/node/697990)
- [Malay Mail: SME Corp on MSME back-end digitalisation](https://www.malaymail.com/news/malaysia/2023/10/19/sme-corp-ceo-urges-malaysian-msmes-to-embrace-digitalisation-close-gap-in-upgrading-business-operations/97195)
- [The Star: e-invoicing threshold raised to RM3m](https://thestar.com.my/news/nation/2026/08/30/over-11-million-businesses-to-benefit-from-higher-e-invoicing-threshold-says-lhdn)
- [OECD: Empowering SMEs in the age of AI](https://www.oecd.org/en/publications/empowering-smes-in-the-age-of-ai_bf5a9816-en.html) — prefer this over vendor statistics in the deck
- [Stealth Agents (vendor): SME AI adoption statistics 2026](https://stealthagents.com/research/ai-adoption-statistics-small-businesses)
- [Eftsure: business email compromise statistics](https://eftsure.com/statistics/business-email-compromise-statistics/)
- [XTransfer (vendor): Malaysia–China payments](https://www.xtransfer.com/blog/malaysia-china-payments)
- [Malay Mail: local-currency trade with China](https://www.malaymail.com/news/malaysia/2026/03/24/anwar-malaysias-local-currency-trade-with-china-thailand-and-indonesia-surges-to-rm82b-cutting-reliance-on-us-dollar/213702)

**Regulation and standards**

- [HHQ: Bank Negara Malaysia's AI discussion paper](https://hhq.com.my/posts/bank-negara-malaysias-discussion-paper-artificial-intelligence-in-the-malaysian-financial-sector)
- [OWASP Top 10 for Agentic Applications 2026 (overview)](https://www.giskard.ai/knowledge/owasp-top-10-for-agentic-application-2026)
- [IETF: OAuth 2.0 for Browser-Based Apps](https://datatracker.ietf.org/doc/draft-ietf-oauth-browser-based-apps/11/)

**China reachability**

- [GreatFire: vercel.app](https://en.greatfire.org/domain/vercel.app) · [run.app](https://en.greatfire.org/domain/run.app) · [supabase.co](https://en.greatfire.org/domain/supabase.co) · [analyzer](https://en.greatfire.org/analyzer)
- [Vercel: Accessing Vercel-hosted sites from mainland China](https://vercel.com/kb/guide/accessing-vercel-hosted-sites-from-mainland-china)
- [Chinafy: Fixing font loading issues in China](https://www.chinafy.com/blog/how-to-fix-font-loading-issues-in-china)

**Data store**

- [Neo4j AuraDB Free](https://neo4j.com/free-graph-database/)
