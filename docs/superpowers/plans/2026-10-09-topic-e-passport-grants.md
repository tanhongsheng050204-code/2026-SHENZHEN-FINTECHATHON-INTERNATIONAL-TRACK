# Plan 6 — Passport, audit packs and external grants

**Implemented:** 2026-10-09. The Passport, audit packs and lender/auditor links are now real.

Each one is:
- computed from the company's records;
- recorded on its tenant workflow hash chain;
- verifiable by anyone who holds the document.

Lender and auditor links expire and can be revoked, and every view is recorded on the audit chain.

## Design

**Where things are stored.** Nothing gets a new table, so there is no migration. Every record is an event on the existing workflow chain (`workflow_audit_log`, append-only, hash-chained, anchored daily). The chain is the only store.

| Event | Contents |
|---|---|
| `passport_issued` | The SHA-256 and the hashed content fields |
| `audit_pack_prepared` | The SHA-256 and the hashed content fields |
| `external_grant_created` | Kind, scope, grantee email **token** (never the email), expiry, `allow_exact_values` |
| `external_grant_revoked` | Closes a grant |
| `external_grant_viewed` | One event per successful view by a lender or auditor |

Grant state (active, revoked or expired) is rebuilt from these events, so the audit trail and the state cannot disagree.

**Passport contents.** Computed from the same cash basis and financing profile as the Cash and Financing pages (Plan 4):
- cash-flow health;
- annual revenue;
- receivables over 90 days;
- validated e-invoice share;
- customer concentration;
- financing facts on record;
- e-invoices validated by MyInvois.

Amounts are always bands, such as "RM2.5M–5M", never exact figures. A fact with no source reads "Not on record". A company on the demo data is labelled "(synthetic demo data)".

**Verification is public.** It:
1. finds the issued event by Passport id;
2. compares hashes and names every changed field;
3. re-verifies the tenant's whole chain;
4. checks that the stored document still hashes to the stored digest;
5. reports the first anchor file whose workflow tail covers the entry.

Anchor files are read from `AUDIT_ANCHOR_DIR`, which defaults to `audit-anchors/` in the repository.

**Share links.** A link is `grant_<16 hex>.<HMAC over grant id and tenant>`, checked in constant time.

| Link | Response |
|---|---|
| Forged or unknown | 404 `grant_not_found` |
| Revoked | 410 `grant_revoked` |
| Expired | 410 `grant_expired` |

Email one-time codes for lenders are not built. The spec allows an expiring signed link as the fallback, and that is what this is.

**Audit packs.** Each pack covers a year or quarter and holds five items, each with its own digest:
- bank lines;
- e-invoice register, with MyInvois UIN count;
- reconciliation, which says plainly that it is not measured yet;
- audit-chain proof;
- payroll, as run totals only, with per-employee lines withheld.

**Routing.** `app/routes/passports_live.py` is registered before the stub router and serves every passport path. Issuing and sharing use Plan 2's `require_step_up` when it is present, and plain role checks until then. The stub handlers are now unreachable and can be deleted after Plan 2 merges.

**Frontend.**
- Financing gains "Issue a Passport" for the owner and "Prepare audit pack" for finance and the owner.
- The shared page explains expired, revoked and invalid links separately.

## Evidence

`backend/tests/test_passports_live.py` has 8 tests on SQLite. They cover:
- recording on the chain;
- recomputable hash and version numbering;
- a one-field tamper named;
- an unknown Passport;
- a tampered chain detected;
- a lender link that works and audits each view;
- revoked links (410), expired links (410) and forged links (404);
- the email never appearing in a response or the chain;
- tenant isolation;
- audit pack hashing and the auditor link;
- role gates;
- anchor discovery.

The full backend suite passes.

## Not done

- **Hosted PostgreSQL.** Not validated. The public verify and view endpoints read the chain across tenants before a tenant context exists, so RLS needs checking on Supabase.
- **Anchors in production.** The production image does not ship `audit-anchors/`. Set `AUDIT_ANCHOR_DIR`, or the API reports no anchor.
- **Exact values.** `allow_exact_values` is recorded on the grant, but Passports carry bands only, so it has no effect yet.
- **Lender email codes.** Not built.
