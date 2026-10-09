"""Render Plan 3 tables from ORM metadata and append explicit PostgreSQL RLS."""

# SQL clauses are kept as complete strings to make the generated policies reviewable.
# ruff: noqa: E501

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base

TABLES = frozenset(
    {
        "import_mappings",
        "business_import_batches",
        "suppliers",
        "supplier_bank_changes",
        "bank_transactions",
        "payables",
        "purchase_orders",
        "inventory_items",
        "stock_snapshots",
        "payroll_runs",
        "payroll_lines",
        "marketing_spend",
        "marketplace_payouts",
        "sales_pipeline",
        "synthetic_tenant_seeds",
    }
)
CHECKS = {
    "import_mappings": [
        "schema_name in ('bank_statement_v1','payables_register_v1','purchase_orders_v1','stock_v1','payroll_v1','marketing_spend_v1','marketplace_payouts_v1','sales_pipeline_v1')",
        "length(header_fingerprint) = 64",
        "jsonb_typeof(column_map) = 'object'",
    ],
    "business_import_batches": [
        "imported_rows >= 0 and duplicate_rows >= 0",
        "length(fingerprint) = 64",
    ],
    "suppliers": ["length(normalized_name) = 64"],
    "supplier_bank_changes": ["status in ('quarantined','verified','rejected')"],
    "bank_transactions": ["direction in ('in','out')", "amount > 0"],
    "payables": [
        "amount >= 0 and amount_myr >= 0 and fx_rate > 0",
        "status in ('open','paid','cancelled')",
    ],
    "purchase_orders": [
        "amount >= 0 and amount_myr >= 0 and fx_rate > 0",
        "status in ('open','received','paid','cancelled')",
    ],
    "inventory_items": ["unit_cost >= 0 and reorder_level >= 0 and lead_time_days >= 0"],
    "stock_snapshots": ["on_hand >= 0"],
    "payroll_runs": [
        "total_gross >= 0 and employer_contributions >= 0",
        "period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
        "status in ('draft','approved','paid')",
    ],
    "payroll_lines": ["gross_band ~ '^AMOUNT_BAND_[0-9]+$'"],
    "marketing_spend": [
        "spend >= 0 and (attributed_revenue is null or attributed_revenue >= 0)",
        "period_end >= period_start",
    ],
    "marketplace_payouts": [
        "gross >= 0 and fees >= 0 and net >= 0 and gross - fees = net",
        "status in ('expected','paid','cancelled')",
    ],
    "sales_pipeline": [
        "stage in ('quote','order','invoiced','lost')",
        "amount >= 0 and probability between 0 and 1",
    ],
    "synthetic_tenant_seeds": [
        "version >= 1",
        "annual_revenue_myr >= 0",
        "manifest ->> 'synthetic' = 'true'",
    ],
}

FINANCE = "public.finbrain_role() in ('owner_director','finance_ops','compliance')"
OWNER = "public.finbrain_role() = 'owner_director'"
FINANCE_WRITE = "public.finbrain_role() in ('owner_director','finance_ops')"


def jobs(*names):
    return "public.plan3_has_job(array[" + ",".join(f"'{n}'" for n in names) + "])"


def main():
    sql = [
        "-- Plan 3: apply after all August migrations and Plan 2. Generated from ORM + explicit RLS.",
        "begin;",
        "set local search_path = public;",
        "alter table public.customers add constraint customers_tenant_id_unique unique (tenant_id, id);",
        "alter table public.structured_ingestion_batches add column tenant_id uuid references public.tenants(id);",
        "update public.structured_ingestion_batches set tenant_id = '00000000-0000-0000-0000-000000000001' where tenant_id is null;",
        "alter table public.structured_ingestion_batches alter column tenant_id set not null;",
        "drop policy finbrain_structured_batches on public.structured_ingestion_batches;",
        "drop policy finbrain_worker_structured_batches on public.structured_ingestion_batches;",
        "create policy finbrain_structured_batches on public.structured_ingestion_batches to finbrain_app using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','finance_ops','compliance')) with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','finance_ops'));",
        "create policy finbrain_worker_structured_batches on public.structured_ingestion_batches to finbrain_worker using (tenant_id = public.finbrain_tenant_id()) with check (tenant_id = public.finbrain_tenant_id());",
    ]
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        if table.name not in TABLES:
            continue
        sql.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda item: item.name):
            sql.append(str(CreateIndex(index).compile(dialect=dialect)) + ";")
        for number, check in enumerate(CHECKS.get(table.name, []), 1):
            sql.append(
                f"alter table public.{table.name} add constraint plan3_{table.name}_{number} check ({check});"
            )
        if "record_hash" in table.columns:
            sql.append(f"alter table public.{table.name} add check (length(record_hash) = 64);")
    sql.extend(
        [
            """create function public.plan3_has_job(jobs text[]) returns boolean
language sql stable set search_path = '' as $$
  select public.finbrain_role() <> 'compliance' and exists (
    select 1 from public.user_roles r where r.user_id = public.finbrain_user_id()
      and r.tenant_id = public.finbrain_tenant_id() and r.active
      and r.job_functions ?| jobs)
$$;""",
            "revoke all on function public.plan3_has_job(text[]) from public;",
            "grant execute on function public.plan3_has_job(text[]) to finbrain_app;",
        ]
    )
    permissions = {
        "import_mappings": ("public.finbrain_role() <> ''", FINANCE_WRITE),
        "business_import_batches": ("public.finbrain_role() <> ''", "public.finbrain_role() <> ''"),
        "suppliers": (
            f"{FINANCE} or {jobs('procurement', 'logistics')}",
            f"{FINANCE_WRITE} or {jobs('procurement', 'logistics')}",
        ),
        "supplier_bank_changes": (FINANCE, FINANCE_WRITE),
        "bank_transactions": (FINANCE, FINANCE_WRITE),
        "payables": (f"{FINANCE} or {jobs('procurement')}", FINANCE_WRITE),
        "purchase_orders": (
            f"{FINANCE} or {jobs('procurement', 'logistics')}",
            f"{OWNER} or {jobs('procurement', 'logistics')}",
        ),
        "inventory_items": (
            f"{FINANCE} or {jobs('procurement', 'logistics', 'operations')}",
            f"{OWNER} or {jobs('procurement', 'logistics')}",
        ),
        "stock_snapshots": (
            f"{FINANCE} or {jobs('procurement', 'logistics', 'operations')}",
            f"{OWNER} or {jobs('procurement', 'logistics')}",
        ),
        "payroll_runs": (f"{FINANCE} or {jobs('hr')}", f"{OWNER} or {jobs('hr')}"),
        "payroll_lines": (f"{OWNER} or {jobs('hr')}", f"{OWNER} or {jobs('hr')}"),
        "marketing_spend": (f"{FINANCE} or {jobs('marketing')}", f"{OWNER} or {jobs('marketing')}"),
        "marketplace_payouts": (
            f"{FINANCE} or {jobs('marketing')}",
            f"{OWNER} or {jobs('marketing')}",
        ),
        "sales_pipeline": (
            f"{FINANCE} or {jobs('sales', 'customer_service')}",
            f"{OWNER} or {jobs('sales', 'customer_service')}",
        ),
        "synthetic_tenant_seeds": ("public.finbrain_role() <> ''", "false"),
    }
    for table in sorted(TABLES):
        read, write = permissions[table]
        sql.extend(
            [
                f"alter table public.{table} enable row level security;",
                f"alter table public.{table} force row level security;",
                f"revoke all on public.{table} from public, anon, authenticated;",
                f"grant select, insert on public.{table} to finbrain_app, finbrain_worker;",
                f"create policy plan3_read on public.{table} for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and ({read}));",
                f"create policy plan3_insert on public.{table} for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and ({write}));",
                f"create policy plan3_worker_read on public.{table} for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());",
                f"create policy plan3_worker_insert on public.{table} for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());",
            ]
        )
        if "id" in Base.metadata.tables[table].columns and table not in {
            "import_mappings",
            "business_import_batches",
        }:
            sql.append(
                f"grant usage, select on sequence public.{table}_id_seq to finbrain_app, finbrain_worker;"
            )
    sql.extend(
        [
            "-- Finance reads aggregate payroll totals; per-employee records are Owner/HR only.",
            "-- No UPDATE/DELETE privileges on the imported financial facts.",
            "grant select, insert on public.customers to finbrain_worker;",
            "create policy plan3_worker_customers_read on public.customers for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());",
            "create policy plan3_worker_customers_insert on public.customers for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());",
            "grant usage, select on sequence public.customers_id_seq to finbrain_worker;",
            "grant select on public.tenant_settings to finbrain_worker;",
            "create policy plan3_worker_settings on public.tenant_settings for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());",
            "commit;",
        ]
    )
    path = (
        Path(__file__).resolve().parents[2]
        / "supabase/migrations/202610090001_business_imports.sql"
    )
    content = "\n\n".join(sql)
    path.write_text(
        "\n".join(line.rstrip() for line in content.splitlines()) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(TABLES)} tables to {path.name}")


if __name__ == "__main__":
    main()
