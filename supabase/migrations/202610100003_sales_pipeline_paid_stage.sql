-- Received sales are kept for the financial analysis (stage 'paid'); they never
-- enter the cash forecast. Widen the Plan 3 stage check to allow them.
begin;

alter table public.sales_pipeline drop constraint if exists plan3_sales_pipeline_1;
alter table public.sales_pipeline add constraint plan3_sales_pipeline_1
  check (stage in ('quote','order','invoiced','paid','lost'));

commit;
