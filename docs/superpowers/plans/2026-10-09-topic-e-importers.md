# Plan 3 — Synthetic tenant and business CSV importers

**Implemented:** 2026-10-09. Backend import pipeline, persistence, mapped CSV schemas,
and local synthetic seed. **Evidence:** the seed command completed against an isolated
SQLite database, importing 53 rows in eight batches. Static checks are recorded below.
Follow-up: automated tests and disposable PostgreSQL/RLS checks now pass. Hosted
Supabase validation remains pending; see `docs/REMAINING_WORK.md` for current evidence.

**Owner:** B3. Depends on Plan 2 identity, tenant settings and vault. Feeds Plan 4
finance calculations and Plan 5 position skills. The Data sources screen now connects
all eight formats to preview, commit and history, with full column mapping support.

## Delivered

- Eight versioned schemas: bank statements, payables, purchase orders, stock,
  payroll, marketing spend, marketplace payouts and sales pipeline.
- Persistent tenant column mappings replace the remaining customization stub.
  The existing three mapping routes retain their response envelopes and now return
  `data_mode: live`.
- Preview and commit APIs validate the same CSV. Commits check again under the
  tenant transaction lock; a preview is informational and is not an authorization grant.
- Fifteen new tenant tables, composite tenant foreign keys and an explicit
  PostgreSQL migration with forced RLS. Financial facts have SELECT/INSERT grants,
  with no UPDATE/DELETE grants for application or worker roles.
- Protected source text and identity fields; salary lines contain employee and
  amount tokens with bands. Payroll totals remain exact for deterministic calculations.
- A non-destructive seed command creates a dedicated, labelled synthetic home-goods
  importer and imports all eight datasets using the same service as the HTTP API.

`live` describes a response read or computed from persistence. Synthetic records
also carry `synthetic: true`; this does not claim the data is real or the service is deployed.

## API and browser flow

The Plan 2 HttpOnly session, CSRF header and allowed-origin checks apply here.
Commit and mapping creation require recent TOTP step-up. No tenant ID comes from
the CSV or request body; the verified principal supplies it.

| Endpoint | Purpose |
| --- | --- |
| `GET /imports/schemas` | Allowed/required columns and importing job functions |
| `GET /imports/batches?schema_name=...&limit=20` | Tenant import history; at most 100 batches |
| `POST /imports/{schema_name}/preview` | Validate values, resolve mapping, report duplicates/conflicts |
| `POST /imports/{schema_name}/commit` | Validate again and atomically persist all accepted facts |
| `GET /settings/import-mappings` | Existing tenant mappings, Owner/Finance |
| `POST /settings/import-mappings` | Save a mapping, Owner/Finance with recent TOTP |
| `POST /settings/import-mappings/match` | Find a mapping for the same schema and normalized headers |

Request for preview and commit:

```json
{
  "csv_text": "date,description,debit,credit,balance,reference\n2026-10-09,SYNTHETIC receipt,0,116400,116400,SYNTHETIC-OPEN\n",
  "mapping_id": null
}
```

Canonical column names work without a saved mapping. For bank-specific/Malay
headers, Finance saves the mapping once. Subsequent imports find it automatically
when `mapping_id` is omitted. An explicit mapping ID must belong to the same tenant,
schema and header fingerprint. The fingerprint includes every header, including
unmapped columns; it ignores order, BOM, Unicode form, outer whitespace and case.
Duplicate, empty and control-character headers are rejected.

Mapping targets are immutable for a given schema/header fingerprint. Re-saving
equivalent targets returns the existing mapping. Different targets return 409;
an audited mapping revision workflow is a future extension.

Preview exposes counts and at most 100 issues `{row, field, code}`. It never echoes
source cell values. `row` is the CSV record number with the header counted as 1;
blank records are ignored. Quoted multiline fields do not use physical line numbering.
Invalid request errors under `/imports` also omit submitted values.

## Schemas and authorization

Owner can import every dataset. Compliance is read-only. Finance can import bank
and payables; other datasets require their job function even when the user is Finance.
The following are required header targets. Empty values are only permitted where a
documented zero/default applies.

| Schema | Required fields | Other fields/defaults | Importing job |
| --- | --- | --- | --- |
| `bank_statement_v1` | date, description, debit, credit | balance, counterparty, reference; blank debit/credit = 0 | Finance role |
| `payables_register_v1` | bill_id, supplier, amount, currency, due_date | fx_rate, status=open, bank_account | Finance role |
| `purchase_orders_v1` | po_no, supplier, amount, currency, expected_delivery, expected_payment | fx_rate, status=open | procurement/logistics |
| `stock_v1` | sku, name, unit_cost, on_hand, snapshot_date | reorder_level=0, lead_time_days=30 | procurement/logistics |
| `payroll_v1` | period, pay_date, employee, gross, employer_contribution | status=draft | hr |
| `marketing_spend_v1` | reference, channel, campaign, spend, period_start, period_end | attributed_revenue | marketing |
| `marketplace_payouts_v1` | reference, platform, payout_date, gross, fees, net | status=expected | marketing |
| `sales_pipeline_v1` | reference, customer, stage, amount, expected_payment_date | probability by stage | sales/customer_service |

Limits and arithmetic:

- UTF-8 JSON text, comma-separated CSV, 2,000,000 UTF-8 bytes, 5,000 nonblank rows,
  40 columns and 4,096 characters per cell. This is a JSON API; the frontend reads
  its file and submits `csv_text`. A reverse proxy should enforce the request-body
  limit before JSON parsing in a deployed environment.
- Dates accept `YYYY-MM-DD` or `DD/MM/YYYY`; slash dates are always day-first.
- Money uses Decimal with two decimal places and numeric(14,2) bounds. Comma
  thousands groups are accepted when quoted in CSV. Scientific notation, NaN,
  infinity and negative amounts are rejected; bank balances may be negative.
- Exactly one bank debit/credit must be positive. For exports with no reference,
  the full normalized transaction is the fallback identity. Truly identical bank
  transactions require distinct references to avoid being treated as duplicates.
- FX accepts MYR, CNY, USD, SGD, EUR, GBP and HKD. MYR defaults to rate 1; foreign
  currencies require a positive explicit MYR-per-unit rate with up to six decimals.
  The converted MYR amount is rounded to cents and checked for overflow.
- Marketplace gross minus fees must equal net; marketing end date must not precede
  start date; counts are nonnegative integers.
- Pipeline defaults: quote=.30, order=.70, invoiced=1.00, lost=.00. An explicit
  probability must be between 0 and 1 with at most two decimals.
- A payroll file must contain the complete run for each period: one pay date and
  status per period. Totals are calculated from distinct employee lines. A run is
  sealed on import; later new lines or changed salaries for it are rejected.
- Stock master definitions are immutable in this importer; new dated snapshots
  can be appended, but changed item definitions need a separate management workflow.

## Persistence, privacy and duplicate handling

The service derives tenant-scoped HMACs for file IDs, row identities, supplier/customer
identities and record contents. Source IDs and conflict hashes do not store raw
identifiers or salaries. Preserve the identity secret across imports; changing it
without migrating identities would invalidate deduplication.

An identical row is skipped. The same source identity with different facts returns
`immutable_record_conflict`. Identical files return a replay result with zero newly
imported rows. A conflicting or malformed row blocks the whole file, so no accepted
subset is silently committed. Corrections are not destructive overwrites; a future
correction workflow must link superseding records explicitly to avoid double counting.

Names, descriptions, references, SKUs and campaign/platform strings are stored as
vault tokens or tenant HMAC identities. `customers` receives a token for its display
name and an HMAC normalized identity; `sales_pipeline.customer_id` references that
existing table with a composite tenant FK. This deliberately does not merge a new
protected identity with a historical plaintext legacy customer automatically.

`TokenizedContent` receives protected non-payroll import records with monetary
bands and typed source references. They remain `protected` rather than claiming
model enrichment or embeddings. No model/provider runs during import.
Payroll lines are excluded from general search content. Per-employee gross values
are encrypted in the employee vault namespace; SQL payroll lines only contain
tokens/bands, and contributions are stored only as run totals. Owner/HR exact
disclosure continues to require the Plan 2 recent-MFA disclosure gate.

Content classified as prompt injection or bank-change instructions blocks the file
and writes a fixed guardrail event on commit. A structured `bank_account` column
creates a **quarantined proposal**, including the first imported account. It never
sets `verified_bank_account_token`. Callback verification and distinct human reviews
belong to the subsequent review workflow.

Every mapping creation and successful import appends a tenant workflow audit event.
Supplier bank-account proposals add their own guardrail events. Raw CSV is not archived.

## Synthetic tenant and local handoff

The seed was executed on 2026-10-09 against:

- Database: `output/finbrain-plan3-synthetic.db` (ignored by Git).
- Tenant: `858f0c1c-42fa-52a2-91b3-80a19d816356`.
- Name: **SYNTHETIC Malaysian Home Goods Importer**.
- Profile revenue: RM2,600,000 per year; Malaysian home goods with Shenzhen suppliers.
- Eight batches: 1 bank row, 4 payables, 2 purchase orders, 3 stock rows,
  30 payroll lines across 3 runs, 1 marketing row, 1 marketplace payout, 11 pipeline rows.
- CSVs and manifest: `output/finbrain-plan3-synthetic/`.

The seed allocates a version/date-specific tenant UUID. Repeating the same seed
uses the same identity; a different as-of date creates a different synthetic tenant.
It refuses to populate an existing tenant without its matching synthetic marker.
It performs no deletes/resets and creates no login, password or membership.

From `backend/`, with the locked environment installed:

```powershell
$env:DATABASE_URL = 'sqlite:///../output/finbrain-plan3-synthetic.db'
# These public development values are only for this fictional local dataset.
$env:TOKEN_ROOT_SECRET = 'development-only-topic-e-synthetic-seed'
$env:TOKEN_HASH_SECRET = 'development-only-topic-e-synthetic-identity'
$env:VAULT_MASTER_KEY = 'development-only-topic-e-synthetic-vault'
$env:ENABLE_GLINER = 'false'
uv run python -m seed.topic_e --as-of 2026-10-09 --export-dir ../output/finbrain-plan3-synthetic
```

For PostgreSQL, apply the migrations to a dedicated demo database, use a controlled
provisioning connection and pass `--allow-postgres`. The command provisions the
tenant, settings and initial vault generation before entering the tenant-scoped
`finbrain_worker` role for the imports. The application role cannot create a vault
key generation, so an active generation must also be provisioned for real imports.
No hosted database was seeded or migrated during this implementation.

### Day-23 basis for AC-01

| Event | Day | Cash change, MYR |
| --- | ---: | ---: |
| Bank closing balance as of 2026-10-09 | 0 | 116,400.00 opening |
| Invoiced pipeline receipt A | 11 | +24,500.00 |
| Rent/utilities payable | 6 | -14,800.00 |
| Invoiced pipeline receipt B | 21 | +18,200.00 |
| Payroll including employer contributions | 23 | -62,000.00 |
| CNY98,000 supplier PO at 0.630000 MYR/CNY | 23 | -61,740.00 |
| **Closing cash / shortfall against RM50,000 minimum** | **23** | **20,560.00 / 29,440.00 gap** |

The seed reads the persisted facts and reconciles the first threshold breach to
day 23, **2026-11-01**. This is a seed reconciliation, not a forecast API or evidence
that the existing Cash page is connected to it.

The ten seeded invoiced pipeline rows contain **likely receipt dates**, including
collection delay already. Plan 4 must not add the delay again. Invoiced pipeline
facts are the seeded receivable source; if they are later also represented as
EInvoiceRecords, link/deduplicate them explicitly. The day-23 supplier payment is
only a purchase order, not also a payable; do not emit a second signal for it.
Stock reorders, scenario bands, probability treatment, downstream alerts and actual
`cash_signals` emission are Plan 4/5 work.

## Files and checks

Core implementation:

- `backend/app/integrations/structured_csv/business_parser.py`
- `backend/app/services/business_imports.py`, `import_mappings.py`
- `backend/app/contracts/imports.py`, extended `customization.py`
- `backend/app/routes/imports.py`, live mappings in `routes/customization.py`
- `backend/app/models.py`, `seed/topic_e.py`
- `supabase/migrations/202610090001_business_imports.sql`
- `docs/api/topic-e-plan-3-openapi.json`

The legacy invoice CSV importer remains available. The last customization stub
module has been removed. `/ingestion-records` now explicitly filters the principal's
tenant in application code as well as relying on PostgreSQL RLS.

Regeneration from `backend/`:

```powershell
uv run python -m scripts.export_plan3_contract
uv run python -m scripts.export_plan3_migration
```

The original Plan 1 contract remains the frozen reference; Plan 3's schema extensions
and six additive/import-mapping paths are exported separately. Frontend integration
must use these additions alongside the Plan 2 authentication protocol.

Checks performed: Ruff on app and the new seed/export scripts, Python compilation,
OpenAPI generation, ORM DDL compilation for SQLite/PostgreSQL, PostgreSQL SQL syntax
parsing, and Git whitespace checks. The local seed execution provides evidence only
for its eight valid synthetic datasets; it does not validate every malformed input,
HTTP MFA/CSRF behavior, concurrency, tenant isolation or hosted RLS policy. Those
need automated/hosted validation before deployment. No test suite was added or run.
