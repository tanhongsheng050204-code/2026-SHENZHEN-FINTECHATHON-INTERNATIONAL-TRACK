-- Rate limits counted in the database, so every API instance shares one count
-- (known risk 6). Identities are stored as keyed hashes, never raw addresses.
-- Only the connection owner uses this table; app roles get no access.
begin;

create table if not exists public.rate_limit_windows (
  bucket text not null,
  identity_hash text not null,
  minute bigint not null,
  hits integer not null default 0,
  primary key (bucket, identity_hash, minute)
);

create index if not exists rate_limit_windows_minute on public.rate_limit_windows (minute);

alter table public.rate_limit_windows enable row level security;
revoke all on public.rate_limit_windows from public, anon, authenticated, finbrain_app, finbrain_worker;

commit;
