# FinBrain OS

**The secure operating system that makes an SME financeable.**

> _AI agents run the finance back office. People review every action. Lenders can verify the result._

![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)
![Frontend](https://img.shields.io/badge/frontend-React_19_+_Vite-61DAFB?logo=react&logoColor=black)
![Database](https://img.shields.io/badge/database-Supabase_Postgres_17_+_pgvector-3FCF8E?logo=supabase&logoColor=white)
![AI](https://img.shields.io/badge/AI-Morpheus_+_Gemini-8A2BE2)
![Security](https://img.shields.io/badge/security-AES--256--GCM_vault_+_RLS-D97706)
![Tests](https://img.shields.io/badge/tests-pytest_offline-2496ED?logo=pytest&logoColor=white)
[![Website](https://img.shields.io/badge/website-finbrainos.vercel.app-black?logo=vercel&logoColor=white)](https://finbrainos.vercel.app/)

**Live site: <https://finbrainos.vercel.app/>**

FinBrain OS is our entry for the **2026 Shenzhen International FinTech Competition
(FinTechathon), International Track — Topic E: SME Finance Copilot**. It gives a small
business an AI finance team that works under human control: agents forecast cash flow, chase
receivables and match financing; owners and staff review what the agents propose; and the
outcome is a privacy-preserving, tamper-evident record that a lender can verify.

It is built on a privacy core that already runs in this repository. Business knowledge from
email, Telegram, uploaded documents, invoice spreadsheets, bank exports and LHDN e-invoices
passes through one protected pipeline: sensitive values are tokenized and encrypted before
any AI model sees them, every answer cites its evidence and adapts to the requester's role,
and every disclosure and decision lands in a hash-chained audit log.

| Briefing | Customers |
| --- | --- |
| ![Briefing dashboard](frontend/public/screenshots/briefing.png) | ![Customer workspace](frontend/public/screenshots/customers.png) |

---

## Table of contents

- [FinTechathon 2026: Topic E](#fintechathon-2026-topic-e)
- [Overview](#overview)
- [How it works](#how-it-works)
- [Features](#features)
- [System architecture](#system-architecture)
- [Security and privacy model](#security-and-privacy-model)
- [Roles and permissions](#roles-and-permissions)
- [Core workflows](#core-workflows)
- [Setup](#setup)
- [Running the system](#running-the-system)
- [Deployment](#deployment)
- [Testing](#testing)
- [Configuration reference](#configuration-reference)
- [Demo and judging](#demo-and-judging)
- [Documentation map](#documentation-map)
- [Scope and known limitations](#scope-and-known-limitations)
- [Contributing](#contributing)

---

## FinTechathon 2026: Topic E

**Theme:** "AI as a Financial Participant." **Topic E brief:** a finance copilot for
small-business owners that matches financing options, manages cash flow with alerts, and
analyses the business's finances.

### Our answer

| Loop | What the SME gets | How it works |
| --- | --- | --- |
| **Operate** | A 30/60/90-day cash-flow forecast with shortfall alerts, and collections that run under review | A deterministic forecast over receivables, payables and bank-statement patterns; the receivables agent drafts reminders that staff approve |
| **Finance** | Financing options matched to the business, each with the reasons it does or does not qualify | Rule-based eligibility over the company's own records, with an application pack drafted for the owner |
| **Trust** | A record a lender can rely on, without exposing customer data | The Financing Readiness Passport: hashed, anchored to a public audit trail, and shared with a lender through a consented, expiring grant |

Three design rules run through all of it:

1. **Code computes, the model narrates.** Forecasts, eligibility and thresholds are
   deterministic code. The language model only routes requests and explains results, and it
   only ever sees tokenized data.
2. **People own decisions.** Every agent action has an autonomy level: read, draft, external
   action (owner approval with a second factor), or money movement (never executed by an
   agent; two different people approve). Agents earn wider autonomy only from their measured
   approval record.
3. **Everything is evidence.** Proposals, reviews, promotions, blocked attacks and lender
   access are entries in a hash-chained, externally anchored audit log.

Why it matters: Malaysia's MSME funding gap is estimated at RM90 billion
([The Edge](https://theedgemalaysia.com/node/697990)), and since 1 September 2026
e-invoicing is mandatory only above RM3 million in annual sales
([The Star](https://thestar.com.my/news/nation/2026/08/30/over-11-million-businesses-to-benefit-from-higher-e-invoicing-threshold-says-lhdn)).
FinBrain therefore treats a validated e-invoice as a credit signal — tamper-proof evidence of
a receivable — and not only as a compliance task.

### Build status

Status as of 2026-10-08. The demo company and its data are synthetic and labelled as such.

| Capability | Status |
| --- | --- |
| Protected ingestion, tokenization, encrypted vault, role-aware disclosure, AI Exposure Receipt | **Built and tested** — see [Features](#features) |
| Cited questions and answers, conversation context, customer intelligence | **Built and tested** |
| Governed outreach, approvals, overdue reminders, e-invoice readiness and PDFs, receivables aging | **Built and tested** |
| Dual hash-chained audit logs with daily external anchoring, PDPA access and erasure, vault rotation | **Built and tested** |
| Topic E API contract served as tested stub endpoints | Planned — target Oct 9 |
| Cash-flow forecast, scenarios and alerts; financing matching with explanations | Planned — target Oct 16 |
| Supervisor agent, review inbox, autonomy ladder and earned autonomy | Planned — target Oct 16 |
| An agent for every SME position — owner, operations, finance, sales, customer service, marketing, purchasing, logistics, HR and compliance — each feeding the cash forecast | Planned — core skills by Oct 16; full skill lists by the November final |
| Company customization: profile, positions and people, approval limits, alerts, templates, import mapping, financing preferences, industry templates | Planned — target Oct 16 |
| Financing Readiness Passport, lender and external-auditor access | Planned — target Oct 16 |
| Email OTP and TOTP sign-in, Team page, agent guardrails, security posture dashboard | Planned — target Oct 16 |
| Evaluation harness and OWASP Agentic Top 10 control map | Planned — target Oct 16 |
| Production agent (manufacturing template); SMS one-time passwords; dashboard layout; automated data retention | Designed, not built |

### How the entry maps to the scoring criteria

| Criterion | Weight | What we will submit as evidence |
| --- | --- | --- |
| Task completion | 40% | An evaluation harness of scripted financial tasks that runs offline in CI, and the live demonstration |
| Security & compliance | 30% | The privacy core, multi-factor sign-in, agent guardrails mapped to the OWASP Top 10 for Agentic Applications (2026), a STRIDE threat model, and the security self-assessment |
| Innovation & interaction | 30% | The review inbox and earned autonomy, the Financing Readiness Passport, and Malaysia and China jurisdiction packs |

### Submission map

| Deliverable | Where it lives |
| --- | --- |
| Technical documentation | This README and the [program design spec](docs/superpowers/specs/2026-10-08-fintechathon-topic-e-sme-finance-copilot-design.md) |
| Presentation deck | Added by Oct 19 |
| Demo video | Added by Oct 19, as an MP4 plus a mirror reachable from mainland China |
| Source code, deployment instructions and tests | This repository — see [Setup](#setup), [Deployment](#deployment) and [Testing](#testing) |
| Security self-assessment | Added by Oct 18 |
| Execution evidence | Evaluation report and audit-chain evidence bundle, added by Oct 19 |

### Program documents

- [The six documents](FINBRAIN_SIX_DOCUMENTS.md) — PRD, TRD, app flow, UI/UX brief, backend
  schema and implementation plan covering every SME position and company customization. Where
  it differs from the spec below, it wins.
- [Program design spec](docs/superpowers/specs/2026-10-08-fintechathon-topic-e-sme-finance-copilot-design.md)
  — positioning, agents, finance engine, security, China reachability, schedule, demo script
  and claims policy.
- [Plan 1: Topic E API contract](docs/superpowers/plans/2026-10-08-topic-e-api-contract.md)
  — revision 2: 48 tested stub endpoints covering every position, customization and external
  sharing; later plans replace each stub with a real service.

---

## Overview

### The problem

Small Malaysian businesses run their finances from Gmail, WhatsApp and Telegram chats,
spreadsheets, invoices and bank exports. They see cash problems late, chase payments by
hand, and find financing hard to get because their records are scattered, private and hard
to verify. Generic AI chatbots can read that information, but they create three
unacceptable risks for a business handling customer personal data:

| Risk | Consequence |
| --- | --- |
| **Data leakage** | Customer names, phone numbers, and invoice amounts are pasted into external AI services |
| **No access control** | Every employee sees everything the model knows |
| **No accountability** | Answers have no evidence, actions have no approval, nothing is auditable |

### The solution

FinBrain enforces all three protections as **architecture, not policy**:

1. Sensitive values are **detected, tokenized, and encrypted before any external model call**.
2. Every answer is **role-aware** and backed by **inspectable evidence citations**.
3. Every disclosure, recommendation, and state change lands in **tamper-evident,
   hash-chained audit logs**.

### Business benefits

| Benefit | How FinBrain delivers it |
| --- | --- |
| **Zero raw-PII exposure to AI vendors** | Deterministic tokens are all that ever leave the process; originals live only in an encrypted, versioned vault |
| **PDPA-aligned by design** | Token-level access export and crypto-shredding erasure; every disclosure is audited |
| **MyInvois-ready operations** | E-invoice readiness scoring, LHDN-style PDFs, UIN issuance, payment receipts |
| **Right answer for every role** | Backend-owned roles, per-entity disclosure policies, format-shaped masks — never silent redactions |
| **Trustworthy answers** | Strict `SOURCE-n` citation validation; invented facts, tokens, and citations are rejected |
| **Human-controlled automation** | Outreach and recommendations require explicit owner approval; nothing external is sent autonomously |
| **Verifiable history** | Dual hash-chained audit logs with append-only triggers, live verification, and daily external anchoring |
| **No vendor lock-in, demo-safe** | Deterministic offline fallbacks for every AI provider; the system runs fully without API keys |
| **Data never leaves the machine** | Local OCR (RapidOCR), local JWT verification, on-premise-able database |

---

## How it works

Every piece of information follows the same protected path:

```mermaid
flowchart TD
    A["Gmail · Telegram · Uploads · Structured CSV · E-invoices · Manual records"] --> B["CanonicalIngestionRecord<br/>one shape for every source"]
    B --> C{"FastAPI privacy boundary<br/>Supabase JWT authorization"}
    C --> D["Detect PII<br/>regex first, GLiNER assist"]
    D --> E["Tokenize<br/>PERSON_a1b2c3d4e5 · AMOUNT_BAND_3_…"]
    E --> F["Encrypt originals<br/>AES-256-GCM token vault"]
    F --> G[("Protected content<br/>Supabase Postgres / SQLite")]
    G --> H["SQL-first filter planner<br/>counts · lists · filters"]
    G --> I["Morpheus / Gemini<br/>protected text only"]
    I --> G
    H --> J["Cited analysis<br/>SOURCE-n validation"]
    J --> K{"Role authorized?"}
    K -- "Yes" --> L["Single-use disclosure session<br/>restore exact values, audited"]
    K -- "No" --> M["Format-shaped masks<br/>RM2.5K–5K · *****@******.***"]
    L --> N["Answer + citations + AI Exposure Receipt"]
    M --> N
    N --> O["Recommendation → approval → implementation"]
    O --> P[("Tamper-evident audit chains")]
```

**The core invariant:** raw sensitive content never reaches a database row, a log line, or
an external AI provider. Only deterministic tokens cross the model boundary, and exact
values are restored only inside the backend, only for authorized roles, one audited grant
at a time.

---

## Features

Everything in this section is built and covered by the offline test suite. The Topic E
finance-copilot capabilities and their status are listed under
[FinTechathon 2026: Topic E](#fintechathon-2026-topic-e).

### Ingestion

| Capability | Details | Benefit |
| --- | --- | --- |
| Unified canonical ingestion | Every source produces the same record: `source_record_id`, `source_system`, `record_type`, `text`, `occurred_at`, `metadata` | One privacy pipeline protects everything; new connectors plug in without new security code |
| Telegram capture bot | Private-chat long polling, operator allowlist, text/forwarded text/TXT/MD/CSV/EML/PDF/DOCX/images, HMAC-signed confirm keyboards | Capture knowledge where it happens — the group chat — without exposing chat IDs |
| Telegram customer onboarding | `/start` privacy notice → name → Gmail → phone → one unified protected profile | Customers self-register through a guided, tokenized flow |
| Gmail / IMAP connector | Read-only, unread-only, UID-cursor sync, HMAC delivery receipts, attachment extraction | Idempotent by construction — no duplicates across restarts and re-syncs |
| Protected file upload | Preview → confirm flow bound by a keyed digest for TXT, MD, CSV, EML, PDF, DOCX, images | What you preview is exactly what gets ingested — no TOCTOU substitution |
| Structured CSV (`invoice_register_v1`) | Strict schema, stable row identity, batch receipts | Spreadsheets become individually queryable, citable records |
| Local OCR | RapidOCR on-device fallback for scanned PDFs and images | Scanned documents are readable without any image leaving the deployment |
| E-invoice extraction | LLM structuring of invoice PDFs with deterministic regex fallback | Manual invoice entry becomes a one-upload affair |

### Intelligence

| Capability | Details | Benefit |
| --- | --- | --- |
| SQL-first questions | Counts and exact listings answered from the database with zero model calls | Deterministic, instant, and free of hallucination for factual lookups |
| Cited semantic analysis | Morpheus/Gemini restricted to supplied `SOURCE-n` evidence | Every claim is verifiable; invented citations, tokens, and PII are rejected |
| Conversational context | 24-hour conversations, six-turn protected window, ordinal/pronoun resolution | "Describe the third one" just works — without leaking earlier context |
| Customer Intelligence Brief | Structured brief: status, cited claims, timeline, missing information, recommended action | A decision-ready view in ten seconds, not a chat paragraph |
| Evidence Drawer | Lazy role-authorized inspection: protected view vs. your permitted view, freshness, withheld-token explanation | Users verify the evidence behind any conclusion in place |
| AI Exposure Receipt | Per-answer proof: model input, protected/restored/withheld counts, role policy, vault generation, grant count | Privacy becomes a visible product feature, not an invisible promise |
| Role comparison | Compliance-only replay of one stored answer under different role policies | Access control is demonstrable without rerunning AI or leaking privilege |
| Customer attention scoring | Deterministic, evidence-backed risk signals (overdue severity, outstanding balance, unresolved actions) | Knows who needs attention today — with every point traceable to evidence |
| Process recommendations | Recurring-problem mining over protected records; query-originated recommendations keep citation lineage | Operational improvement proposals emerge from evidence, not guesswork |

### Governed action

| Capability | Details | Benefit |
| --- | --- | --- |
| Recommendation workflow | `proposed → approved → implemented` / `rejected`; owner-only decisions; tokenized comments | Insight becomes accountable action with a human decision point |
| Governed outreach | Email and Telegram responses through `draft → pending_approval → approved → sending → sent → replied` | Nothing reaches a customer without explicit owner approval |
| Reply correlation | Inbound `In-Reply-To`/`References` matched by HMAC to outbound actions; sender identity must match | Replies attach to the right customer — mismatches are quarantined, never guessed |
| Overdue payment reminders | Deterministic Telegram planner per tenant policy (grace, interval, cap, approval) | Collections follow-up is consistent, capped, and idempotent |
| E-invoice readiness | MyInvois-oriented scoring, LHDN-style invoice PDF, official payment receipt, owner UIN issuance | Submission blockers surface before LHDN rejects them |
| PDPA subject rights | Token-level access export and crypto-shredding erasure, both audited | Data-subject requests are one audited operation |

### Trust

| Capability | Details | Benefit |
| --- | --- | --- |
| Dual audit chains | Separate hash-chained disclosure and workflow logs, append-only DB triggers, live verification | Any edit or deletion breaks the chain — visibly |
| External anchoring | Daily GitHub Actions commit of each tenant's chain tail | Tamper evidence survives even a compromised database |
| Versioned token vault | Random wrapped generations, per-token HKDF keys, resumable rotation, optional auto-rotation worker | Key compromise has a bounded blast radius and a recovery path |
| Service transparency | Unauthenticated `/status` page with per-worker status, uptime, heartbeats | Operations health is observable at a glance |

---

## System architecture

```mermaid
flowchart LR
    subgraph Client["Browser — React SPA"]
        UI["Workspaces & protected chat"]
        SA["Supabase Auth JS"]
    end
    subgraph Supabase["Supabase project"]
        AUTH["Auth — RS256/ES256 JWT"]
        PG[("Postgres 17 + pgvector<br/>forced RLS · append-only audits")]
        ST["Storage — invoice PDFs"]
    end
    subgraph Backend["FastAPI backend"]
        API["REST API + RLS context"]
        PE["Privacy engine<br/>detect → tokenize → vault"]
        PDF["PDF renderer<br/>invoice + receipt"]
    end
    subgraph ExtAI["External AI — protected text only"]
        MOR["Morpheus<br/>reasoning"]
        GEM["Gemini<br/>embeddings"]
    end
    subgraph Workers["Background workers"]
        TG["Telegram poller"]
        EM["Email IMAP/SMTP"]
        VR["Vault rotation"]
        RS["Recommendations scheduler"]
    end
    UI --> API
    SA --> AUTH
    API --> PE
    PE --> PG
    PE -. "tokens only" .-> MOR
    PE -. "tokens only" .-> GEM
    API --> PDF --> ST
    TG --> PG
    EM --> PG
    VR --> PG
    RS --> PG
```

### Components

| Component | Technology | Responsibility |
| --- | --- | --- |
| Frontend | React 19 + TypeScript + Vite SPA | Auth UI, chat, workspaces (Customers, e-Invoicing, Finance, Approvals, Sources, Audit), evidence/exposure UX, en/ms/zh i18n |
| API backend | FastAPI + SQLAlchemy 2.0, Python 3.12 | Privacy boundary, authorization, business logic, PDF generation |
| Reasoning | Morpheus (OpenAI-compatible) | Protected summaries, cited answers, outreach drafts |
| Embeddings / fallback | Google Gemini | 768-dimensional embeddings, structured-output reasoning fallback |
| Database | Supabase Postgres 17 + pgvector (HNSW) | All persistence; SQLite for zero-config local development and tests |
| Auth | Supabase Auth (email/password) | Identity; asymmetric JWTs verified locally by the backend |
| Workers | Same codebase, separate processes | Telegram polling, email sync/send, vault rotation, recommendations scheduling |
| Hosting | Google Cloud (backend, Docker) + Vercel (frontend) | Deployment |

### Repository layout

```text
FinBrain/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, middleware, CORS, /health
│   │   ├── config.py            # Typed settings (pydantic-settings)
│   │   ├── db.py                # Engine, sessions, RLS context management
│   │   ├── models.py            # 34 SQLAlchemy models
│   │   ├── schemas.py           # Pydantic request/response contracts
│   │   ├── observability.py     # JSON logging, Sentry (PII-safe)
│   │   ├── auth/                # JWT verification, principal, role dependencies
│   │   ├── routes/              # 15 routers (query, ingestion, outreach, …)
│   │   ├── services/            # Domain logic (ingestion, reasoning, outreach, …)
│   │   ├── security/            # Detection, tokenization, vault, disclosure, rotation
│   │   └── integrations/        # telegram/, email_connector/, structured_csv/, ocr/
│   ├── scripts/                 # Operational CLI utilities
│   ├── seed/                    # Demo dataset and reset logic
│   └── tests/                   # Offline, deterministic test suite
├── frontend/
│   └── src/                     # Screens, components, API client, auth, i18n
├── supabase/migrations/         # 32 forward-only SQL migrations
├── infra/supabase/              # Schema/RLS reference snapshots
├── scripts/                     # PowerShell demo lifecycle (start/check/stop)
├── demo/                        # Synthetic judging fixtures
├── docs/superpowers/            # Feature specs and implementation plans
├── .github/workflows/           # CI and audit-chain anchoring
├── Dockerfile                   # Backend container (API + workers)
└── docker/entrypoint.sh         # Worker supervision inside the container
```

### Request flow

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant S as Supabase Auth
    participant B as FastAPI
    participant D as Postgres (RLS)
    U->>S: signIn(email, password)
    S-->>U: access token (RS256, user_role + tenant_id claims)
    U->>B: API call + Bearer token
    B->>S: JWKS lookup (cached 10 min)
    B->>B: verify signature · issuer · audience · expiry
    B->>D: load role from backend-owned user_roles
    alt stale role claim
        B-->>U: 403 stale_user_role_claim
    else valid
        B->>D: SET app.* context · SET ROLE finbrain_app
        B-->>U: response under forced row-level security
    end
```

The frontend holds only the Supabase publishable key; the database password, service-role
key, and token secrets never leave the backend. Background workers run the same code as
`finbrain_worker` with worker-scoped context.

---

## Security and privacy model

### Detection

- **Deterministic regex first**: Malaysian NRIC, mobile numbers, email addresses, bank
  account numbers, `RM` amounts.
- **Optional GLiNER (ML)** adds person, organization, address, and card detections
  (threshold 0.4), post-filtered to remove role words ("Customer", "Unassigned") and
  malformed emails. Regex wins overlaps; GLiNER failure degrades gracefully to regex-only.
- **Fail-closed gate**: `contains_known_pii` blocks every external model call and every
  persistence of generated artifacts.

### Tokenization

- Every sensitive value becomes `{LABEL}_{hmac10}` — e.g. `PERSON_a1b2c3d4e5` — derived
  as HMAC-SHA256 over `tenant_id + value`: deterministic within a tenant (the same
  customer matches across sources), collision-proof across tenants.
- Monetary values are **band-aware**: `RM4,500` and `RM 4500.00` normalize to the same
  `AMOUNT_BAND_3_…` token. Nine bands (`<RM500` … `RM100K+`) are visible to models and
  unauthorized roles; the exact value lives only in the vault.
- Telegram identities get dedicated `TGUSER` / `TGCHAT` token types — raw chat IDs never
  persist.

### Token vault

A three-tier key hierarchy (all HKDF-SHA256 / AES-256-GCM):

1. **Master wrapping key** — derived from `VAULT_MASTER_KEY`, never stored.
2. **Generation keys** — random 32 bytes per `vault_key_versions` row, wrapped under the
   master key with version-bound AAD.
3. **Per-token data keys** — HKDF from the generation key, bound to token + version.

Ciphertext AAD binds every vault row to its token, entity type, source record, and key
version — ciphertext cannot be swapped between rows. **Rotation** activates a fresh
generation, demotes the old one to decrypt-only, re-encrypts rows in resumable
advisory-locked batches, then retires the empty generation. Crash recovery reopens
stranded generations automatically.

### Disclosure

Restoring an exact value is a deliberate, bounded event:

```mermaid
sequenceDiagram
    autonumber
    participant B as Backend
    participant S as Disclosure session (in-memory)
    participant V as Token vault
    participant A as Audit chain
    B->>S: open — bound to query hash + actor + role + turn
    loop per token
        B->>V: fetch ciphertext (RLS-gated)
        alt role authorized
            V-->>B: ciphertext
            B->>S: issue single-use grant (AES-GCM, context-bound AAD)
            B->>S: consume grant (replay impossible)
            B->>A: append ALLOW event
        else denied
            B->>A: append DENY event
        end
    end
    B->>S: close — session secret wiped
```

Grants live for 30 seconds, are bound to their session context cryptographically, and are
single-use. Unauthorized roles receive format-shaped masks (`RM2.5K–5K`,
`*****@*******.***`) — never silent redactions. **Every allow and deny is audited.**

### Database hardening

- RLS is enabled **and forced** on all 34 tables; `anon`/`authenticated` grants are
  revoked — the Supabase Data API is dark.
- `finbrain_app` and `finbrain_worker` are non-`BYPASSRLS` roles; policies read
  transaction-scoped `app.*` settings, and the vault policy enforces the per-token role
  allowlist *inside the database*.
- Audit tables reject `UPDATE` / `DELETE` via triggers.
- Multi-tenant isolation end-to-end: `tenant_id` on every business table, tenant-scoped
  policies, tenant-scoped HMAC tokens, per-tenant audit chains.

---

## Roles and permissions

Roles are assigned by administrators in the backend-owned `user_roles` table and delivered
inside Supabase access tokens via a custom auth hook. The frontend only *displays* the
authenticated role — it can never grant one.

| Capability | general_employee | finance_ops | owner_director | compliance |
| --- | :---: | :---: | :---: | :---: |
| Ask questions, view own conversations | Yes | Yes | Yes | Yes |
| Ingest records / upload files / sync email | — | Yes | Yes | — |
| View finance & e-invoice workspaces | — | Yes | Yes | Yes |
| Create / edit outreach drafts | — | Yes | Yes | — |
| Approve / reject outreach & recommendations | — | — | Yes | — |
| Approve & submit e-invoices (assign UIN) | — | — | Yes | — |
| View audit chains | — | — | — | Yes |
| Role comparison over stored answers | — | — | — | Yes |
| Privacy export / erasure | — | — | — | Yes |

Exact-value disclosure is governed independently per entity type (the vault ACL policy) —
bank account numbers require `finance_ops` or above, card numbers are compliance-only,
while names and phones are visible to all authenticated roles.

Four demonstration accounts are provisioned for evaluation —
`employee@`, `finance@`, `compliance@`, `owner@finbrain-demo.test`
(see [CUSTOMER_OUTREACH_GUIDE.md](./CUSTOMER_OUTREACH_GUIDE.md) for credentials and setup).

---

## Core workflows

### 7.1 Protected ingestion

```mermaid
flowchart TD
    A["Source payload"] --> B{"source_record_id<br/>PII-free?"}
    B -- "No" --> X["Reject — opaque IDs only"]
    B -- "Yes" --> C["HMAC fingerprint<br/>idempotency check"]
    C -- "Already ready, unchanged" --> Z["Short-circuit — no duplicates"]
    C -- "New or changed" --> D["Detect PII<br/>regex + GLiNER"]
    D --> E["Tokenize<br/>deterministic, tenant-scoped"]
    E --> F["Encrypt originals<br/>AES-256-GCM vault"]
    F --> G["Persist protected row<br/>status: protected"]
    G --> H["Summarize protected text"]
    H --> I{"Summary valid?<br/>no invented tokens · no residual PII"}
    I -- "No" --> J["status: failed_enrichment<br/>bounded auto-retry"]
    I -- "Yes" --> K["Embed protected text + summary<br/>768-dim"]
    K --> L["status: ready — queryable and citable"]
```

Enrichment failures leave a retryable `failed_enrichment` row; a bounded sweep retries
them using only persisted protected content. Identical payloads short-circuit via the
keyed fingerprint.

### 7.2 Asking questions — `POST /query`

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant F as FastAPI
    participant D as Postgres
    participant AI as Morpheus / Gemini
    participant V as Token vault
    U->>F: question + conversation? + customer scope?
    F->>D: deterministic intent plan + allowlisted filters
    Note over F: counts & listings answered here — no AI call
    F->>F: tokenize question (detector + registry-confirmed entities)
    F->>D: retrieve protected evidence (SQL / pgvector hybrid)
    opt conversational follow-up
        F->>F: six-turn context · ordinal & pronoun resolution
    end
    F->>AI: cited reasoning over SOURCE-n protected blocks
    AI-->>F: answer + citations
    F->>F: validate — unknown citations, tokens, PII all rejected
    F->>D: persist protected turn + exact citations
    F->>V: role-gated detokenization (single-use grants)
    V-->>F: exact values or format-shaped masks
    F-->>U: answer + citations + brief + AI Exposure Receipt
```

Seven deterministic intents — `count_records`, `count_sources`, `list_records`,
`list_sources`, `lookup`, `semantic`, `analyze_all` — decide the execution path before
tokenization. Counts and exact listings never call a model; `analyze_all` processes every
eligible record in protected batches of 20.

### 7.3 Recommendation → approval

```mermaid
stateDiagram-v2
    [*] --> proposed: process analysis / query brief / verification gap
    proposed --> approved: owner approves
    proposed --> rejected: owner rejects
    approved --> implemented: owner marks implemented
```

Recommendations carry evidence, expected benefit, owner, success metric, priority, and
confidence. Query-originated recommendations keep their exact turn, query-hash, and
citation lineage. Every decision writes a workflow-audit event; comments are tokenized.

### 7.4 Governed customer outreach

```mermaid
stateDiagram-v2
    [*] --> draft: manual or AI-generated from protected evidence
    draft --> pending_approval: submit — verified endpoint + confirmed customer
    draft --> cancelled: cancel
    pending_approval --> approved: owner approves
    pending_approval --> rejected: owner rejects
    approved --> sending: worker claims (FOR UPDATE SKIP LOCKED)
    sending --> sent: provider accepted
    sending --> failed: error before delivery
    sending --> delivery_unknown: interrupted — never auto-retried
    sent --> replied: In-Reply-To hash + sender token match
```

Safety guards: the AI draft sees only protected evidence; invented facts, contact-misuse
lines, and model-added signatures are scrubbed; the recipient is decrypted only inside the
worker at send time; a reply from a mismatched sender is recorded as `identity_conflict`
and never attached to the wrong customer.

### 7.5 Customer identity and attention

First-time email senders become **provisional customers** keyed by their protected
address. Display-name and self-identification claims are recorded as reviewable evidence —
a conflicting later name triggers **owner review**, never a silent rename. Attention
scoring is a pure, fingerprint-idempotent function over three evidence-backed signals:

| Signal | Points | Condition |
| --- | --- | --- |
| Overdue invoice | 10–40 | Validated, unpaid, past due — severity by days overdue |
| Outstanding balance | 5–15 | Validated unpaid total ≥ RM 1,000 |
| Action-required records | 8–30 (capped) | Linked records flagged by the summarizer, freshness-decayed |

Score thresholds: `≥70 urgent · ≥40 high · ≥15 monitoring · else healthy`. Every signal
links to its evidence row.

### 7.6 E-invoice lifecycle

```mermaid
stateDiagram-v2
    [*] --> review: supplier TIN missing
    [*] --> pending: TIN present
    review --> pending: TIN supplied (Fix & Edit)
    pending --> validated: owner approves — UIN assigned
```

Payment state (`mark_paid`) is orthogonal to document status. Readiness scoring flags
missing supplier TINs (critical) and supplier-name inconsistencies (warnings) before LHDN
does. The system renders LHDN-style invoice PDFs and official payment receipts
("Resit Rasmi") and can generate request-fix drafts to suppliers through the approvals
queue.

### 7.7 PDPA subject rights

- **Access** — export a token's decrypted value plus every record referencing it
  (compliance-only, audited).
- **Erasure** — crypto-shredding: the vault ciphertext is deleted while registry metadata
  survives, so every past and future reference degrades to its masked form. Audited.

---

## Setup

### Prerequisites

| Requirement | Notes |
| --- | --- |
| Windows PowerShell | Demo lifecycle scripts; macOS/Linux work via the manual path |
| Python 3.12+ | Managed with [uv](https://docs.astral.sh/uv/) |
| Node.js 18+ / npm | Frontend build |
| Morpheus API key | Protected reasoning — optional; offline fallback exists |
| Gemini API key | 768-dim embeddings — optional; offline fallback exists |
| Optional | Supabase CLI, Telegram bot token, Gmail app password |

### Step 1 — Install dependencies

From the repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Backend (uv manages the environment automatically)
Set-Location backend
uv sync --extra dev
Set-Location ..

# Frontend
Set-Location frontend
npm.cmd ci
Set-Location ..
```

The standard install includes GLiNER and CPU PyTorch.

<details>
<summary><b>Advanced: reuse a workstation CUDA build of PyTorch</b></summary>

```powershell
uv venv .venv --system-site-packages --prompt FinBrain
& .\.venv\Scripts\Activate.ps1
Set-Location backend
uv sync --active --extra dev --no-install-package torch
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Use `uv run --active --no-sync …` afterward so uv does not replace the inherited build.
Demo scripts detect the root `.venv` automatically; override with `FINBRAIN_PYTHON`.

</details>

### Step 2 — Generate the three token secrets

`backend/.env` is git-ignored. **Never commit API keys, tokens, passwords, database URIs,
or these secrets.** Production readiness requires three *distinct* 32-byte values:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLower()
```

| Secret | Purpose |
| --- | --- |
| `TOKEN_ROOT_SECRET` | Application fingerprints and actor references |
| `TOKEN_HASH_SECRET` | Stable token identity — key rotation never changes tokens |
| `VAULT_MASTER_KEY` | Wraps random database-resident vault generations |

### Step 3 — Configure `backend/.env`

Copy the example and fill in the secrets:

```powershell
Copy-Item backend\.env.example backend\.env
```

Minimum working configuration:

```dotenv
TOKEN_ROOT_SECRET=<generated>
TOKEN_HASH_SECRET=<generated-independent>
VAULT_MASTER_KEY=<generated-independent>
MORPHEUS_API_KEY=<your-key>            # omit to run in offline-demo mode
MORPHEUS_BASE_URL=https://api.mor.org/api/v1
MORPHEUS_MODEL=deepseek-v4-flash
GEMINI_API_KEY=<your-key>              # omit to run in offline-demo mode
GEMINI_REASONING_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
ALLOW_OFFLINE_DEMO=true
DATABASE_URL=sqlite:///./finbrain.db
LOG_LEVEL=INFO
```

Verify Gemini connectivity:

```powershell
Set-Location backend
uv run --active --no-sync python -m scripts.check_gemini
```

### Step 4 — Choose the database

**Option A — local SQLite (default, zero-config).** Tables are created at startup; skip to
Step 6.

**Option B — Supabase Postgres (production path).**

1. Create a Supabase project; keep automatic RLS enabled.
2. Link and push migrations (or apply `supabase/migrations/*.sql` in timestamp order via
   the SQL editor):

   ```powershell
   npx.cmd supabase login
   npx.cmd supabase link --project-ref YOUR_PROJECT_REF
   npx.cmd supabase db push
   ```

3. Copy the exact URI from **Dashboard → Connect** into `backend/.env`:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@POOLER_HOST:5432/postgres?sslmode=require
   ```

4. Verify the deployed schema:

   ```powershell
   uv run --active --no-sync python -m scripts.check_supabase
   ```

> **Staging:** there is no dedicated staging project yet. For pre-release testing, create
> a second Supabase project, push the same migrations, and point a separate environment
> file at it — never test schema changes against production.

### Step 5 — Configure authentication

Follow [AUTH_SETUP.md](./AUTH_SETUP.md). In short:

1. Use **asymmetric JWT signing** (RS256/ES256) — the backend verifies tokens through the
   project JWKS endpoint; no shared secret needed.
2. Enable the **Custom Access Token Hook** pointing at
   `public.custom_access_token_hook` — it injects `user_role` and `tenant_id` into new
   access tokens.
3. Create users in the Supabase dashboard, then insert one `user_roles` row per user
   (role + tenant). Sign out/in after role changes so the claim refreshes.
4. Set in `backend/.env`: `SUPABASE_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`,
   `SUPABASE_JWT_ALGORITHMS=RS256,ES256`.
5. Set in `frontend/.env`:

   ```dotenv
   VITE_API_URL=http://127.0.0.1:8000
   VITE_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
   VITE_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
   ```

### Step 6 — Seed demonstration data

```powershell
Set-Location backend
uv run --active --no-sync python -m seed.seed_data
```

This ingests a twelve-record, six-source synthetic dataset through the *real* protected
pipeline, plus twenty e-invoice records with readiness cases and generated PDFs.

### Step 7 — Verify the installation

```powershell
# Backend — from backend/
uv run --active --no-sync python -m pytest          # full offline test suite
uv run --active --no-sync python -m ruff check .

# Frontend — from frontend/
npm.cmd run lint
npm.cmd run build
```

### Step 8 — Start

Continue to [Running the system](#running-the-system).

---

## Running the system

### One-command demonstration (Windows)

```powershell
& .\scripts\prepare_demo.ps1     # pre-flight: deps, secrets, detector warm, tests, build
& .\scripts\run_demo.ps1         # start everything
& .\scripts\check_demo.ps1       # health report
& .\scripts\stop_demo.ps1        # validated shutdown
```

| Service | URL |
| --- | --- |
| Frontend | <http://127.0.0.1:5173> |
| API + Swagger docs | <http://127.0.0.1:8000/docs> |
| Service status page | <http://127.0.0.1:8000/status> |

The launcher also starts the Telegram long-polling worker (when `TELEGRAM_BOT_TOKEN` is
set), the email worker (when `EMAIL_CONNECTOR_ENABLED=true`), and the vault-rotation
worker (when `VAULT_AUTO_ROTATION_ENABLED=true`). Process ownership is validated by PID +
start time + executable before anything is stopped; logs land in `.runtime/logs`;
`prepare_demo.ps1` never resets the database.

### Run components manually

```powershell
# Backend
Set-Location backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (second terminal)
Set-Location ..\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort

# Optional workers (third terminal, from backend/)
uv run python -m app.integrations.telegram.runner
uv run python -m app.integrations.email_connector.runner
uv run python -m app.security.rotation_runner
```

### Connector setup

**Telegram** — create a bot with BotFather, then:

```dotenv
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_OPERATOR_ROLES=<numeric-user-id>:owner_director
```

Send `/whoami` to the bot to learn your ID. Enable customer onboarding with
`TELEGRAM_CUSTOMER_ONBOARDING_ENABLED=true`; enable outbound responses/reminders with
`TELEGRAM_OUTBOUND_ENABLED=true`. Run only **one** poller per bot token.

**Gmail / IMAP** — enable 2-step verification, create an app password:

```dotenv
EMAIL_CONNECTOR_ENABLED=true
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_IMAP_USERNAME=your-account@gmail.com
EMAIL_IMAP_PASSWORD=<16-char app password>
EMAIL_SYNC_INTERVAL_SECONDS=60
```

Sync is read-only (unread messages newer than the saved UID cursor). Outbound email
additionally requires `OUTBOUND_EMAIL_ENABLED=true` and the `EMAIL_SMTP_*` variables.

### Resetting demonstration data

```powershell
Set-Location backend
uv run --active --no-sync python -m seed.seed_data --refresh          # re-protect + re-embed
uv run --active --no-sync python -m seed.seed_data --reset --yes      # clear app rows, reseed
uv run --active --no-sync python -m scripts.check_demo_data           # verify demo + vault + chains
```

`--reset` clears application data (protected content, vault, receipts, recommendations,
audit) while preserving schema, migrations, and RLS. Use `--exclude-source email` to
preserve live-ingested Gmail records.

---

## Deployment

### Backend — Google Cloud (Docker)

```powershell
docker build -t finbrain-backend -f Dockerfile .
docker run --rm -p 8000:8000 --env-file backend\.env finbrain-backend
```

The container runs the API as the main process plus auto-restarting loops for each enabled
worker (Telegram, email, vault rotation, recommendations scheduler). `/health` is the
container healthcheck (300 s timeout to allow the first GLiNER model download). Provide the
same `backend/.env` values as deployment environment variables. Run only **one** Telegram
poller per bot token — disable the deployed Telegram worker while testing locally.

### Frontend — Vercel

Set the Vercel project root to `frontend/` (`vercel.json` configures the Vite build with
an SPA fallback). Build-time variables:

```dotenv
VITE_API_URL=https://<your-backend-domain>
VITE_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
```

On the backend, add the Vercel domain to `CORS_ORIGINS` (or match it with
`CORS_ORIGIN_REGEX`), and add the Vercel URL to Supabase Auth's redirect URLs.

### CI/CD

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `ci.yml` | every push / PR | Backend: `ruff check` + full `pytest` (SQLite, no secrets). Frontend: `tsc -b` + `eslint` + production build. Gates merges only. |
| `anchor-audit-chain.yml` | daily 00:00 UTC + manual | Writes each tenant's audit-chain tail to `audit-anchors/<date>.json` and commits it — tamper evidence outside the database trust boundary. Requires the `PRODUCTION_DATABASE_URL` repository secret (read-only). |

---

## Testing

Backend (from `backend/`):

```powershell
uv run --active --no-sync python -m pytest
uv run --active --no-sync python -m ruff check app tests seed scripts
```

Frontend (from `frontend/`):

```powershell
npm.cmd run lint
npm.cmd run build
```

The suite is **fully offline and deterministic**: GLiNER is disabled, provider keys are
emptied, and every fallback is deterministic — tests never touch the network, download
models, or call an AI provider. Coverage spans:

- ingestion guarantees (only protected content reaches models; vault ciphertext never
  contains raw values);
- role-gated disclosure, single-use grants, and both audit chains;
- vault rotation, crash recovery, and tenant isolation;
- connector idempotency, reconciliation, and reply correlation;
- outreach and reminder state machines, e-invoice readiness and PDFs;
- conversation context resolution and query intent planning;
- RLS / authorization boundaries.

The complete manual verification procedure (live Gmail, Telegram, persona disclosure,
approval journeys, Supabase SQL checks) is in
[TESTING_GUIDE.md](./TESTING_GUIDE.md).

---

## Configuration reference

All settings live in `backend/app/config.py` with mirrors in `backend/.env.example`.

| Group | Variables |
| --- | --- |
| Secrets | `TOKEN_ROOT_SECRET`, `TOKEN_HASH_SECRET`, `VAULT_MASTER_KEY` (three distinct values required for production readiness) |
| Database | `DATABASE_URL`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT` |
| Reasoning | `MORPHEUS_API_KEY`, `MORPHEUS_BASE_URL`, `MORPHEUS_MODEL`, `MORPHEUS_TIMEOUT_SECONDS`, `GEMINI_API_KEY`, `GEMINI_REASONING_MODEL`, `GEMINI_EMBEDDING_MODEL`, `GEMINI_TIMEOUT_SECONDS` |
| Vault rotation | `VAULT_AUTO_ROTATION_ENABLED`, `VAULT_ROTATION_INTERVAL_DAYS`, `VAULT_ROTATION_CHECK_SECONDS`, `VAULT_ROTATION_BATCH_SIZE` |
| Detection | `ENABLE_GLINER`, `GLINER_MODEL_NAME`, `GLINER_DEVICE`, `PREWARM_GLINER_ON_STARTUP` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OPERATOR_ROLES`, `TELEGRAM_ALLOWED_CHAT_TYPES`, `TELEGRAM_DRAFT_TTL_SECONDS`, `TELEGRAM_CUSTOMER_ONBOARDING_ENABLED`, `TELEGRAM_OUTBOUND_ENABLED`, `TELEGRAM_REMINDER_INTERVAL_SECONDS`, `TELEGRAM_DELETE_SOURCE_AFTER_INGEST`, file/size/page limits |
| Email | `EMAIL_CONNECTOR_ENABLED`, `EMAIL_IMAP_*`, `EMAIL_SYNC_INTERVAL_SECONDS`, `EMAIL_MAX_MESSAGES_PER_SYNC`, `EMAIL_INCLUDE_ATTACHMENTS`, `OUTBOUND_EMAIL_ENABLED`, `EMAIL_SMTP_*`, `EMAIL_REPLY_CORRELATION_ENABLED` |
| Feature flags | `CUSTOMER_INTELLIGENCE_ENABLED`, `CUSTOMER_ATTENTION_ENABLED`, `RECOMMENDATIONS_AUTO_ANALYSIS_ENABLED`, `CONVERSATION_PLANNER_ENABLED` |
| Supabase | `SUPABASE_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`, `SUPABASE_JWT_ALGORITHMS` (RS256/ES256 only), `SUPABASE_SERVICE_ROLE_KEY` (server-side only), `EINVOICE_DOCUMENT_BUCKET` |
| Structured CSV limits | `STRUCTURED_CSV_MAX_FILE_BYTES`, `STRUCTURED_CSV_MAX_ROWS`, `STRUCTURED_CSV_MAX_COLUMNS`, `STRUCTURED_CSV_MAX_CELL_CHARS` |
| Observability | `LOG_LEVEL`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` (PII transmission is hardcoded off) |
| Runtime | `ALLOW_OFFLINE_DEMO`, `CORS_ORIGINS`, `CORS_ORIGIN_REGEX`, `APPLICATION_TIMEZONE`, `SERVICE_INSTANCE_ID` |

---

## Demo and judging

The `demo/` directory contains synthetic, clearly-labeled fixtures:

| File | Purpose |
| --- | --- |
| `chat_upload_invoice_register.csv` | Direct chat-upload fixture (4 invoice rows; CHAT-INV-4001 demonstrates band-vs-exact disclosure) |
| `invoice_register.csv` | Gmail-attachment variant of the same dataset |
| `invoice_register_invalid.csv` | Negative fixture exercising row-level validation codes |
| `sample_approval_email.eml` | RFC-822 email fixture for protected upload |
| `customer_followup.txt` | Plain-text upload fixture |
| `gmail_test_messages.md` | Copy-paste synthetic Gmail messages for live connector rehearsal |
| `judging_questions.md` | The eight-question demonstration script plus persona-comparison steps |
| `expected_results.md` | Acceptance expectations for each demo step |

### Suggested demonstration flow

This flow uses features that are built today. The Topic E demonstration — six acts in about
six minutes — is scripted in section 13 of the
[program design spec](docs/superpowers/specs/2026-10-08-fintechathon-topic-e-sme-finance-copilot-design.md)
and replaces this flow once those features land.

1. Sign in as finance/operations; sync unread Gmail.
2. Upload `chat_upload_invoice_register.csv`; inspect the protected preview; confirm.
3. Ask `Show all email sources` — deterministic citation cards, no model call.
4. Open a citation; compare the protected evidence with your authorized view.
5. Ask a cross-source analytical question; inspect the AI Exposure Receipt.
6. Create a recommendation from the cited result; sign in as owner and approve it.
7. Open Audit; verify both hash chains.

---

## Documentation map

| Document | Contents |
| --- | --- |
| [FINBRAIN_SIX_DOCUMENTS.md](./FINBRAIN_SIX_DOCUMENTS.md) | Topic E master document: PRD, TRD, app flow, UI/UX brief, backend schema, implementation plan, contradictions resolved and decisions log |
| [Program design spec](docs/superpowers/specs/2026-10-08-fintechathon-topic-e-sme-finance-copilot-design.md) | FinTechathon 2026 Topic E: positioning, scope tiers, agents, finance engine, security, China reachability, schedule, demo script, claims policy |
| [Plan 1: Topic E API contract](docs/superpowers/plans/2026-10-08-topic-e-api-contract.md) | Test-first plan that serves the frozen Topic E API contract as stub endpoints |
| [SUPABASE_ARCHITECTURE.md](./SUPABASE_ARCHITECTURE.md) | **Required reading for database contributors** — schema contract, RLS boundaries, change rules, emergency procedure |
| [SUPABASE_SCHEMA_REFERENCE.md](./SUPABASE_SCHEMA_REFERENCE.md) | Column-level disaster-recovery snapshot of the live schema |
| [AUTH_SETUP.md](./AUTH_SETUP.md) | Supabase Auth, JWT signing, custom token hook, user provisioning |
| [TESTING_GUIDE.md](./TESTING_GUIDE.md) | Full manual verification runbook |
| [CUSTOMER_OUTREACH_GUIDE.md](./CUSTOMER_OUTREACH_GUIDE.md) | Customer intelligence + governed outreach: pipeline, roles, acceptance tests |
| [FIVE_FEATURE_PRODUCT_PLAN.md](./FIVE_FEATURE_PRODUCT_PLAN.md) | Product rationale for the five-feature intelligence package |
| [FIVE_FEATURE_IMPLEMENTATION_PLAN.md](./FIVE_FEATURE_IMPLEMENTATION_PLAN.md) / [FIVE_FEATURE_COMPLETION_REPORT.md](./FIVE_FEATURE_COMPLETION_REPORT.md) | Implementation plan and verified completion state |
| [INDUSTRIAL_ROADMAP_PLAN.md](./INDUSTRIAL_ROADMAP_PLAN.md) | Gap assessment and the eight-phase hardening roadmap (CI, tenancy, retrieval, observability, PDPA, anchoring) |
| [PRIORITY.md](./PRIORITY.md) | Original hackathon priorities and blueprint |
| [EINVOICE_READINESS_PLAN.md](./EINVOICE_READINESS_PLAN.md) | e-Invoice feature plan and shipped scope |
| `docs/superpowers/specs/` · `docs/superpowers/plans/` | Per-feature design specs and TDD plans |
| `infra/supabase/README.md` | Connection guidance and security boundary notes |

---

## Scope and known limitations

This is a proof of concept. The following boundaries are deliberate and documented:

- **Multi-tenancy** is implemented at the schema/policy level (tenants, tenant-scoped
  tokens, per-tenant audit chains) but connectors still share one worker identity;
  per-tenant credentials are deferred.
- **Finance and e-invoice screens** contain demonstration-only sample data alongside the
  live API path.
- **Audit chains are tamper-evident, not tamper-proof** — hash-linked and append-only
  inside the database, externally anchored via CI, but a privileged database administrator
  remains inside the trust boundary. No digital signatures.
- **Email** uses IMAP app-password authentication; provider OAuth is deferred.
- **The analytical policy** retrieves every eligible record for cross-source questions
  (batched at 20) — correctness over production-scale latency. pgvector retrieval is live
  for semantic questions.
- **Production operations** still require a managed KMS/HSM for the vault wrapping key,
  backups, monitoring, incident response, formal PDPA review, and adversarial privacy
  testing.
- **Deferred connectors**: WhatsApp Business, banking APIs, Google Drive/SharePoint.
  Scanned-image OCR runs locally (RapidOCR); cloud OCR providers are deferred.
- **The web-search control** in the chat UI is visual only.
- **Reachability from mainland China**: the live frontend is served from `vercel.app`, which
  is mostly blocked in mainland China; the browser signs in directly against `supabase.co`,
  which is intermittently disrupted there; and the page loads Google Fonts, which is
  blocked. Custom domains, self-hosted fonts and backend-mediated sign-in are planned
  (program spec, section 9).
- **E-invoice business names**: `einvoice_records` stores supplier and buyer business names
  in clear. A sole proprietor's business name can be a person's name, so this is listed as a
  known risk to tokenize or to document.

---

## Contributing

1. Read [SUPABASE_ARCHITECTURE.md](./SUPABASE_ARCHITECTURE.md) before touching Supabase,
   persistence, identity, ingestion, or workers — it defines the schema contract, the
   twelve database change rules, and required pre-merge validation.
2. **Never edit an applied migration** — add the next timestamped migration, and update
   the SQLAlchemy models, `scripts/check_supabase.py`, and the schema reference in the
   same change.
3. **Never store raw PII** in new columns or JSON; route text and metadata through the
   protection layer.
4. **Never weaken RLS** to fix application code, and never expose direct table access to
   the browser.
5. Run the full verification before merge:

   ```powershell
   # backend/
   uv run --active --no-sync python -m pytest
   uv run --active --no-sync python -m ruff check .
   # frontend/
   npm.cmd run lint
   npm.cmd run build
   ```

6. **Keep demonstrations honest**: label synthetic data as synthetic, report fallback
   modes visibly (`offline-demo` vs `morpheus`/`gemini`), and never claim simulated
   integrations are live.

---

<div align="center">

**FinBrain OS** - AI agents run the finance back office, people review every action, and
lenders can verify the result, with customer data protected before any AI sees it.

[finbrainos.vercel.app](https://finbrainos.vercel.app/)

</div>
