-- Plan 3: apply after all August migrations and Plan 2. Generated from ORM + explicit RLS.

begin;

set local search_path = public;

alter table public.customers add constraint customers_tenant_id_unique unique (tenant_id, id);

alter table public.structured_ingestion_batches add column tenant_id uuid references public.tenants(id);

update public.structured_ingestion_batches set tenant_id = '00000000-0000-0000-0000-000000000001' where tenant_id is null;

alter table public.structured_ingestion_batches alter column tenant_id set not null;

drop policy finbrain_structured_batches on public.structured_ingestion_batches;

drop policy finbrain_worker_structured_batches on public.structured_ingestion_batches;

create policy finbrain_structured_batches on public.structured_ingestion_batches to finbrain_app using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','finance_ops','compliance')) with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','finance_ops'));

create policy finbrain_worker_structured_batches on public.structured_ingestion_batches to finbrain_worker using (tenant_id = public.finbrain_tenant_id()) with check (tenant_id = public.finbrain_tenant_id());

CREATE TABLE import_mappings (
	id VARCHAR NOT NULL,
	tenant_id UUID NOT NULL,
	schema_name VARCHAR NOT NULL,
	name VARCHAR(60) NOT NULL,
	column_map JSONB NOT NULL,
	header_fingerprint VARCHAR(64) NOT NULL,
	created_by UUID,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, schema_name, header_fingerprint),
	UNIQUE (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.import_mappings add constraint plan3_import_mappings_1 check (schema_name in ('bank_statement_v1','payables_register_v1','purchase_orders_v1','stock_v1','payroll_v1','marketing_spend_v1','marketplace_payouts_v1','sales_pipeline_v1'));

alter table public.import_mappings add constraint plan3_import_mappings_2 check (length(header_fingerprint) = 64);

alter table public.import_mappings add constraint plan3_import_mappings_3 check (jsonb_typeof(column_map) = 'object');

CREATE TABLE inventory_items (
	sku VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	unit_cost NUMERIC(14, 2) NOT NULL,
	reorder_level INTEGER NOT NULL,
	lead_time_days INTEGER NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, sku),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.inventory_items add constraint plan3_inventory_items_1 check (unit_cost >= 0 and reorder_level >= 0 and lead_time_days >= 0);

CREATE TABLE suppliers (
	normalized_name VARCHAR(64) NOT NULL,
	name_token VARCHAR NOT NULL,
	country VARCHAR(2),
	currency VARCHAR(3) NOT NULL,
	verified_bank_account_token VARCHAR,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, normalized_name),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.suppliers add constraint plan3_suppliers_1 check (length(normalized_name) = 64);

CREATE TABLE synthetic_tenant_seeds (
	tenant_id UUID NOT NULL,
	version INTEGER NOT NULL,
	as_of DATE NOT NULL,
	annual_revenue_myr NUMERIC(14, 2) NOT NULL,
	manifest JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (tenant_id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.synthetic_tenant_seeds add constraint plan3_synthetic_tenant_seeds_1 check (version >= 1);

alter table public.synthetic_tenant_seeds add constraint plan3_synthetic_tenant_seeds_2 check (annual_revenue_myr >= 0);

alter table public.synthetic_tenant_seeds add constraint plan3_synthetic_tenant_seeds_3 check (manifest ->> 'synthetic' = 'true');

CREATE TABLE business_import_batches (
	id VARCHAR NOT NULL,
	tenant_id UUID NOT NULL,
	schema_name VARCHAR NOT NULL,
	mapping_id VARCHAR,
	fingerprint VARCHAR(64) NOT NULL,
	imported_rows INTEGER NOT NULL,
	duplicate_rows INTEGER NOT NULL,
	synthetic BOOLEAN NOT NULL,
	created_by UUID,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	FOREIGN KEY(tenant_id, mapping_id) REFERENCES import_mappings (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.business_import_batches add constraint plan3_business_import_batches_1 check (imported_rows >= 0 and duplicate_rows >= 0);

alter table public.business_import_batches add constraint plan3_business_import_batches_2 check (length(fingerprint) = 64);

CREATE TABLE supplier_bank_changes (
	supplier_id BIGINT NOT NULL,
	proposed_account_token VARCHAR NOT NULL,
	source_record_id VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	callback_verified_by UUID,
	maker_id UUID,
	checker_id UUID,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id, supplier_id) REFERENCES suppliers (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.supplier_bank_changes add constraint plan3_supplier_bank_changes_1 check (status in ('quarantined','verified','rejected'));

CREATE TABLE bank_transactions (
	posted_on DATE NOT NULL,
	description_token TEXT NOT NULL,
	direction VARCHAR NOT NULL,
	amount NUMERIC(14, 2) NOT NULL,
	balance NUMERIC(14, 2),
	counterparty_token VARCHAR,
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX bank_transactions_tenant_date ON bank_transactions (tenant_id, posted_on);

alter table public.bank_transactions add constraint plan3_bank_transactions_1 check (direction in ('in','out'));

alter table public.bank_transactions add constraint plan3_bank_transactions_2 check (amount > 0);

alter table public.bank_transactions add check (length(record_hash) = 64);

CREATE TABLE marketing_spend (
	channel VARCHAR NOT NULL,
	campaign_label VARCHAR NOT NULL,
	spend NUMERIC(14, 2) NOT NULL,
	period_start DATE NOT NULL,
	period_end DATE NOT NULL,
	attributed_revenue NUMERIC(14, 2),
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX marketing_spend_tenant_period ON marketing_spend (tenant_id, period_start);

alter table public.marketing_spend add constraint plan3_marketing_spend_1 check (spend >= 0 and (attributed_revenue is null or attributed_revenue >= 0));

alter table public.marketing_spend add constraint plan3_marketing_spend_2 check (period_end >= period_start);

alter table public.marketing_spend add check (length(record_hash) = 64);

CREATE TABLE marketplace_payouts (
	platform VARCHAR NOT NULL,
	payout_date DATE NOT NULL,
	gross NUMERIC(14, 2) NOT NULL,
	fees NUMERIC(14, 2) NOT NULL,
	net NUMERIC(14, 2) NOT NULL,
	status VARCHAR NOT NULL,
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX marketplace_payouts_tenant_date ON marketplace_payouts (tenant_id, payout_date);

alter table public.marketplace_payouts add constraint plan3_marketplace_payouts_1 check (gross >= 0 and fees >= 0 and net >= 0 and gross - fees = net);

alter table public.marketplace_payouts add constraint plan3_marketplace_payouts_2 check (status in ('expected','paid','cancelled'));

alter table public.marketplace_payouts add check (length(record_hash) = 64);

CREATE TABLE payables (
	supplier_id BIGINT NOT NULL,
	bill_no VARCHAR NOT NULL,
	amount NUMERIC(14, 2) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	fx_rate NUMERIC(12, 6),
	amount_myr NUMERIC(14, 2) NOT NULL,
	due_date DATE NOT NULL,
	status VARCHAR NOT NULL,
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id, supplier_id) REFERENCES suppliers (tenant_id, id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX payables_tenant_due ON payables (tenant_id, due_date);

alter table public.payables add constraint plan3_payables_1 check (amount >= 0 and amount_myr >= 0 and fx_rate > 0);

alter table public.payables add constraint plan3_payables_2 check (status in ('open','paid','cancelled'));

alter table public.payables add check (length(record_hash) = 64);

CREATE TABLE payroll_runs (
	batch_id VARCHAR NOT NULL,
	period VARCHAR(7) NOT NULL,
	pay_date DATE NOT NULL,
	total_gross NUMERIC(14, 2) NOT NULL,
	employer_contributions NUMERIC(14, 2) NOT NULL,
	status VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, period),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.payroll_runs add constraint plan3_payroll_runs_1 check (total_gross >= 0 and employer_contributions >= 0);

alter table public.payroll_runs add constraint plan3_payroll_runs_2 check (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$');

alter table public.payroll_runs add constraint plan3_payroll_runs_3 check (status in ('draft','approved','paid'));

CREATE TABLE purchase_orders (
	supplier_id BIGINT NOT NULL,
	po_no VARCHAR NOT NULL,
	amount NUMERIC(14, 2) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	fx_rate NUMERIC(12, 6),
	amount_myr NUMERIC(14, 2) NOT NULL,
	expected_delivery DATE NOT NULL,
	expected_payment DATE NOT NULL,
	status VARCHAR NOT NULL,
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id, supplier_id) REFERENCES suppliers (tenant_id, id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX purchase_orders_tenant_payment ON purchase_orders (tenant_id, expected_payment);

alter table public.purchase_orders add constraint plan3_purchase_orders_1 check (amount >= 0 and amount_myr >= 0 and fx_rate > 0);

alter table public.purchase_orders add constraint plan3_purchase_orders_2 check (status in ('open','received','paid','cancelled'));

alter table public.purchase_orders add check (length(record_hash) = 64);

CREATE TABLE sales_pipeline (
	customer_id BIGINT NOT NULL,
	customer_token VARCHAR NOT NULL,
	stage VARCHAR NOT NULL,
	amount NUMERIC(14, 2) NOT NULL,
	expected_payment_date DATE NOT NULL,
	probability NUMERIC(3, 2) NOT NULL,
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id, customer_id) REFERENCES customers (tenant_id, id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX sales_pipeline_tenant_stage ON sales_pipeline (tenant_id, stage);

alter table public.sales_pipeline add constraint plan3_sales_pipeline_1 check (stage in ('quote','order','invoiced','lost'));

alter table public.sales_pipeline add constraint plan3_sales_pipeline_2 check (amount >= 0 and probability between 0 and 1);

alter table public.sales_pipeline add check (length(record_hash) = 64);

CREATE TABLE stock_snapshots (
	item_id BIGINT NOT NULL,
	on_hand INTEGER NOT NULL,
	snapshot_date DATE NOT NULL,
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id, item_id) REFERENCES inventory_items (tenant_id, id),
	UNIQUE (tenant_id, item_id, snapshot_date),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.stock_snapshots add constraint plan3_stock_snapshots_1 check (on_hand >= 0);

alter table public.stock_snapshots add check (length(record_hash) = 64);

CREATE TABLE payroll_lines (
	run_id BIGINT NOT NULL,
	employee_token VARCHAR NOT NULL,
	gross_amount_token VARCHAR NOT NULL,
	gross_band VARCHAR NOT NULL,
	source_record_id VARCHAR NOT NULL,
	record_hash VARCHAR(64) NOT NULL,
	batch_id VARCHAR NOT NULL,
	id BIGSERIAL NOT NULL,
	tenant_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id, run_id) REFERENCES payroll_runs (tenant_id, id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, source_record_id),
	FOREIGN KEY(tenant_id, batch_id) REFERENCES business_import_batches (tenant_id, id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

alter table public.payroll_lines add constraint plan3_payroll_lines_1 check (gross_band ~ '^AMOUNT_BAND_[0-9]+$');

alter table public.payroll_lines add check (length(record_hash) = 64);

create function public.plan3_has_job(jobs text[]) returns boolean
language sql stable set search_path = '' as $$
  select public.finbrain_role() <> 'compliance' and exists (
    select 1 from public.user_roles r where r.user_id = public.finbrain_user_id()
      and r.tenant_id = public.finbrain_tenant_id() and r.active
      and r.job_functions ?| jobs)
$$;

revoke all on function public.plan3_has_job(text[]) from public;

grant execute on function public.plan3_has_job(text[]) to finbrain_app;

alter table public.bank_transactions enable row level security;

alter table public.bank_transactions force row level security;

revoke all on public.bank_transactions from public, anon, authenticated;

grant select, insert on public.bank_transactions to finbrain_app, finbrain_worker;

create policy plan3_read on public.bank_transactions for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance')));

create policy plan3_insert on public.bank_transactions for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops')));

create policy plan3_worker_read on public.bank_transactions for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.bank_transactions for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.bank_transactions_id_seq to finbrain_app, finbrain_worker;

alter table public.business_import_batches enable row level security;

alter table public.business_import_batches force row level security;

revoke all on public.business_import_batches from public, anon, authenticated;

grant select, insert on public.business_import_batches to finbrain_app, finbrain_worker;

create policy plan3_read on public.business_import_batches for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() <> ''));

create policy plan3_insert on public.business_import_batches for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() <> ''));

create policy plan3_worker_read on public.business_import_batches for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.business_import_batches for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

alter table public.import_mappings enable row level security;

alter table public.import_mappings force row level security;

revoke all on public.import_mappings from public, anon, authenticated;

grant select, insert on public.import_mappings to finbrain_app, finbrain_worker;

create policy plan3_read on public.import_mappings for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() <> ''));

create policy plan3_insert on public.import_mappings for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops')));

create policy plan3_worker_read on public.import_mappings for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.import_mappings for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

alter table public.inventory_items enable row level security;

alter table public.inventory_items force row level security;

revoke all on public.inventory_items from public, anon, authenticated;

grant select, insert on public.inventory_items to finbrain_app, finbrain_worker;

create policy plan3_read on public.inventory_items for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['procurement','logistics','operations'])));

create policy plan3_insert on public.inventory_items for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['procurement','logistics'])));

create policy plan3_worker_read on public.inventory_items for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.inventory_items for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.inventory_items_id_seq to finbrain_app, finbrain_worker;

alter table public.marketing_spend enable row level security;

alter table public.marketing_spend force row level security;

revoke all on public.marketing_spend from public, anon, authenticated;

grant select, insert on public.marketing_spend to finbrain_app, finbrain_worker;

create policy plan3_read on public.marketing_spend for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['marketing'])));

create policy plan3_insert on public.marketing_spend for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['marketing'])));

create policy plan3_worker_read on public.marketing_spend for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.marketing_spend for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.marketing_spend_id_seq to finbrain_app, finbrain_worker;

alter table public.marketplace_payouts enable row level security;

alter table public.marketplace_payouts force row level security;

revoke all on public.marketplace_payouts from public, anon, authenticated;

grant select, insert on public.marketplace_payouts to finbrain_app, finbrain_worker;

create policy plan3_read on public.marketplace_payouts for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['marketing'])));

create policy plan3_insert on public.marketplace_payouts for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['marketing'])));

create policy plan3_worker_read on public.marketplace_payouts for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.marketplace_payouts for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.marketplace_payouts_id_seq to finbrain_app, finbrain_worker;

alter table public.payables enable row level security;

alter table public.payables force row level security;

revoke all on public.payables from public, anon, authenticated;

grant select, insert on public.payables to finbrain_app, finbrain_worker;

create policy plan3_read on public.payables for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['procurement'])));

create policy plan3_insert on public.payables for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops')));

create policy plan3_worker_read on public.payables for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.payables for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.payables_id_seq to finbrain_app, finbrain_worker;

alter table public.payroll_lines enable row level security;

alter table public.payroll_lines force row level security;

revoke all on public.payroll_lines from public, anon, authenticated;

grant select, insert on public.payroll_lines to finbrain_app, finbrain_worker;

create policy plan3_read on public.payroll_lines for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['hr'])));

create policy plan3_insert on public.payroll_lines for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['hr'])));

create policy plan3_worker_read on public.payroll_lines for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.payroll_lines for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.payroll_lines_id_seq to finbrain_app, finbrain_worker;

alter table public.payroll_runs enable row level security;

alter table public.payroll_runs force row level security;

revoke all on public.payroll_runs from public, anon, authenticated;

grant select, insert on public.payroll_runs to finbrain_app, finbrain_worker;

create policy plan3_read on public.payroll_runs for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['hr'])));

create policy plan3_insert on public.payroll_runs for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['hr'])));

create policy plan3_worker_read on public.payroll_runs for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.payroll_runs for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.payroll_runs_id_seq to finbrain_app, finbrain_worker;

alter table public.purchase_orders enable row level security;

alter table public.purchase_orders force row level security;

revoke all on public.purchase_orders from public, anon, authenticated;

grant select, insert on public.purchase_orders to finbrain_app, finbrain_worker;

create policy plan3_read on public.purchase_orders for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['procurement','logistics'])));

create policy plan3_insert on public.purchase_orders for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['procurement','logistics'])));

create policy plan3_worker_read on public.purchase_orders for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.purchase_orders for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.purchase_orders_id_seq to finbrain_app, finbrain_worker;

alter table public.sales_pipeline enable row level security;

alter table public.sales_pipeline force row level security;

revoke all on public.sales_pipeline from public, anon, authenticated;

grant select, insert on public.sales_pipeline to finbrain_app, finbrain_worker;

create policy plan3_read on public.sales_pipeline for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['sales','customer_service'])));

create policy plan3_insert on public.sales_pipeline for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['sales','customer_service'])));

create policy plan3_worker_read on public.sales_pipeline for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.sales_pipeline for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.sales_pipeline_id_seq to finbrain_app, finbrain_worker;

alter table public.stock_snapshots enable row level security;

alter table public.stock_snapshots force row level security;

revoke all on public.stock_snapshots from public, anon, authenticated;

grant select, insert on public.stock_snapshots to finbrain_app, finbrain_worker;

create policy plan3_read on public.stock_snapshots for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['procurement','logistics','operations'])));

create policy plan3_insert on public.stock_snapshots for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() = 'owner_director' or public.plan3_has_job(array['procurement','logistics'])));

create policy plan3_worker_read on public.stock_snapshots for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.stock_snapshots for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.stock_snapshots_id_seq to finbrain_app, finbrain_worker;

alter table public.supplier_bank_changes enable row level security;

alter table public.supplier_bank_changes force row level security;

revoke all on public.supplier_bank_changes from public, anon, authenticated;

grant select, insert on public.supplier_bank_changes to finbrain_app, finbrain_worker;

create policy plan3_read on public.supplier_bank_changes for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance')));

create policy plan3_insert on public.supplier_bank_changes for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops')));

create policy plan3_worker_read on public.supplier_bank_changes for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.supplier_bank_changes for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.supplier_bank_changes_id_seq to finbrain_app, finbrain_worker;

alter table public.suppliers enable row level security;

alter table public.suppliers force row level security;

revoke all on public.suppliers from public, anon, authenticated;

grant select, insert on public.suppliers to finbrain_app, finbrain_worker;

create policy plan3_read on public.suppliers for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops','compliance') or public.plan3_has_job(array['procurement','logistics'])));

create policy plan3_insert on public.suppliers for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() in ('owner_director','finance_ops') or public.plan3_has_job(array['procurement','logistics'])));

create policy plan3_worker_read on public.suppliers for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.suppliers for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.suppliers_id_seq to finbrain_app, finbrain_worker;

alter table public.synthetic_tenant_seeds enable row level security;

alter table public.synthetic_tenant_seeds force row level security;

revoke all on public.synthetic_tenant_seeds from public, anon, authenticated;

grant select, insert on public.synthetic_tenant_seeds to finbrain_app, finbrain_worker;

create policy plan3_read on public.synthetic_tenant_seeds for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and (public.finbrain_role() <> ''));

create policy plan3_insert on public.synthetic_tenant_seeds for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and (false));

create policy plan3_worker_read on public.synthetic_tenant_seeds for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_insert on public.synthetic_tenant_seeds for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

-- Finance reads aggregate payroll totals; per-employee records are Owner/HR only.

-- No UPDATE/DELETE privileges on the imported financial facts.

grant select, insert on public.customers to finbrain_worker;

create policy plan3_worker_customers_read on public.customers for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

create policy plan3_worker_customers_insert on public.customers for insert to finbrain_worker with check (tenant_id = public.finbrain_tenant_id());

grant usage, select on sequence public.customers_id_seq to finbrain_worker;

grant select on public.tenant_settings to finbrain_worker;

create policy plan3_worker_settings on public.tenant_settings for select to finbrain_worker using (tenant_id = public.finbrain_tenant_id());

commit;
