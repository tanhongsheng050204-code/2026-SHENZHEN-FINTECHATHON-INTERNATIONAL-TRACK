-- Text that tries to instruct the AI (prompt injection) is stored as
-- 'quarantined' so no agent ever reads it. Widen the check to allow it; without
-- this, a quarantined comment, upload or chat message fails to save.
begin;

alter table public.tokenized_content
  drop constraint if exists tokenized_content_processing_status_valid;
alter table public.tokenized_content
  add constraint tokenized_content_processing_status_valid
    check (processing_status in ('protected', 'ready', 'failed_enrichment', 'quarantined'));

commit;
