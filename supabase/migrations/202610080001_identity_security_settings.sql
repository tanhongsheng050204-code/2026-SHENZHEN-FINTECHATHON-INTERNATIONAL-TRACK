-- Plan 2: backend-only sessions, tenant Team, versioned settings and security controls.
-- Apply after the August migrations. Provider credentials never get app-role grants.

alter table public.token_vault add column data_class text not null default 'customer_personal';
alter table public.protected_token_registry add column data_class text not null default 'customer_personal';

alter table public.user_roles
  add column job_functions jsonb not null default '[]'::jsonb,
  add column display_name text not null default 'Team member',
  add column email_masked text not null default '[restricted]',
  add column mfa_enrolled boolean not null default false,
  add column last_active_at timestamptz,
  add column session_generation integer not null default 0;

update public.user_roles set job_functions = case user_role
  when 'owner_director' then '["owner"]'::jsonb
  when 'finance_ops' then '["finance"]'::jsonb
  when 'compliance' then '["compliance"]'::jsonb
  else '[]'::jsonb end;

alter table public.user_roles add constraint valid_job_functions check (
  jsonb_typeof(job_functions) = 'array' and jsonb_array_length(job_functions) <= 11
  and job_functions <@ '["owner","operations","finance","sales","customer_service","marketing","procurement","logistics","production","hr","compliance"]'::jsonb
  and (not job_functions ? 'owner' or user_role = 'owner_director')
);

create table public.backend_auth_sessions (
  id text primary key check (length(id) = 64),
  csrf_hash text not null check (length(csrf_hash) = 64),
  user_id uuid references auth.users(id) on delete cascade,
  tenant_id uuid references public.tenants(id),
  purpose text not null check (purpose in ('signin','signup','invite','recovery')),
  email_verified boolean not null default false,
  password_verified boolean not null default false,
  credential_ciphertext bytea not null,
  credential_nonce bytea not null,
  generation integer not null default 0,
  aal text not null default 'aal1' check (aal in ('aal1','aal2')),
  mfa_verified_at timestamptz,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz
);
create index backend_auth_sessions_user_idx on public.backend_auth_sessions(user_id, tenant_id);

create table public.tenant_settings (
  tenant_id uuid primary key references public.tenants(id),
  version integer not null check (version >= 1),
  document jsonb not null check (
    document ?& array['profile','positions','approvals','alerts','financing','security','branding']
    and (document -> 'security') ?& array['session_idle_minutes','mfa_required_roles']
    and (document -> 'alerts') ?& array['critical_alerts_enabled','recipients']
    and
    (document #>> '{security,session_idle_minutes}')::integer between 5 and 60
    and (document #> '{security,mfa_required_roles}') @> '["owner_director","finance_ops","compliance"]'::jsonb
    and (document #>> '{alerts,critical_alerts_enabled}')::boolean
    and (document #> '{alerts,recipients}') ? 'owner'
  )
);
create table public.tenant_settings_versions (
  tenant_id uuid not null references public.tenants(id),
  version integer not null,
  document jsonb not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, version)
);
create table public.tenant_setting_changes (
  id text primary key,
  tenant_id uuid not null references public.tenants(id),
  area text not null,
  status text not null check (status in ('pending_approval','applied','rejected')),
  requires_approval boolean not null,
  base_version integer not null,
  version integer not null,
  proposed_document jsonb not null,
  preview jsonb not null,
  proposer_id uuid not null references auth.users(id),
  reviewer_id uuid references auth.users(id),
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  check (reviewer_id is null or reviewer_id <> proposer_id)
);
create index tenant_setting_changes_tenant_idx on public.tenant_setting_changes(tenant_id, created_at desc);

create table public.tenant_customizations (
  id text primary key,
  tenant_id uuid not null references public.tenants(id),
  kind text not null check (kind in ('message_template','alert_rule')),
  document jsonb not null,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create index tenant_customizations_tenant_idx on public.tenant_customizations(tenant_id, kind);

create table public.security_guardrail_events (
  id text primary key,
  tenant_id uuid not null references public.tenants(id),
  agent_id text,
  owasp_code text not null,
  title text not null,
  detail text not null,
  outcome text not null check (outcome in ('blocked','quarantined','escalated')),
  occurred_at timestamptz not null default now()
);
create index security_guardrail_events_tenant_idx on public.security_guardrail_events(tenant_id, occurred_at desc);
create table public.agent_security_controls (
  tenant_id uuid not null references public.tenants(id),
  agent_id text not null,
  engaged boolean not null default false,
  updated_by uuid not null references auth.users(id),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, agent_id)
);
create table public.agent_budget_windows (
  tenant_id uuid not null references public.tenants(id),
  agent_id text not null,
  day date not null,
  tool_calls integer not null default 0 check (tool_calls >= 0),
  spent numeric(14,2) not null default 0 check (spent >= 0),
  primary key (tenant_id, agent_id, day)
);

-- All tables are forced through RLS. Backend pre-auth session lookup uses the
-- existing trusted database connection, before entering finbrain_app. No browser
-- or worker can select credentials, ciphertext or CSRF hashes.
do $$ declare name text; begin
  foreach name in array array['backend_auth_sessions','tenant_settings','tenant_settings_versions',
    'tenant_setting_changes','tenant_customizations','security_guardrail_events',
    'agent_security_controls','agent_budget_windows'] loop
    execute format('alter table public.%I enable row level security', name);
    execute format('alter table public.%I force row level security', name);
    execute format('revoke all on public.%I from anon, authenticated, finbrain_app, finbrain_worker', name);
  end loop;
end $$;

grant select on public.user_roles to finbrain_app;
drop policy if exists finbrain_tenants_read on public.tenants;
create policy plan2_tenants_app_read on public.tenants for select to finbrain_app
  using (id = public.finbrain_tenant_id());
create policy plan2_tenants_worker_read on public.tenants for select to finbrain_worker
  using (true);
grant insert, update on public.user_roles to finbrain_app;
create policy plan2_members_read on public.user_roles for select to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and
    (user_id = public.finbrain_user_id() or public.finbrain_role() in ('owner_director','compliance')));
create policy plan2_members_insert on public.user_roles for insert to finbrain_app
  with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director');
create policy plan2_members_update on public.user_roles for update to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director')
  with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director');

-- Enough columns for Owner session counts, without granting secret access.
grant select (id,user_id,tenant_id,revoked_at,expires_at,generation) on public.backend_auth_sessions to finbrain_app;
create policy plan2_session_counts on public.backend_auth_sessions for select to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director');

grant select, insert, update on public.tenant_settings, public.tenant_setting_changes to finbrain_app;
grant select, insert on public.tenant_settings_versions to finbrain_app;
do $$ declare name text; begin
  foreach name in array array['tenant_settings','tenant_settings_versions','tenant_setting_changes'] loop
    execute format('create policy plan2_settings_read on public.%I for select to finbrain_app using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in (''owner_director'',''finance_ops'',''compliance''))', name);
    execute format('create policy plan2_settings_insert on public.%I for insert to finbrain_app with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in (''owner_director'',''finance_ops'',''compliance''))', name);
  end loop;
end $$;
create policy plan2_settings_update on public.tenant_settings for update to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','compliance'))
  with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','compliance'));
create policy plan2_changes_update on public.tenant_setting_changes for update to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'compliance')
  with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'compliance');

grant select, insert, update on public.tenant_customizations to finbrain_app;
create policy plan2_customizations_read on public.tenant_customizations for select to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','finance_ops','compliance'));
create policy plan2_customizations_insert on public.tenant_customizations for insert to finbrain_app
  with check (tenant_id = public.finbrain_tenant_id() and created_by = public.finbrain_user_id()
    and (public.finbrain_role() = 'owner_director' or (kind = 'message_template' and public.finbrain_role() = 'finance_ops')));
create policy plan2_customizations_update on public.tenant_customizations for update to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director')
  with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director');

grant select, insert on public.security_guardrail_events to finbrain_app, finbrain_worker;
create policy plan2_events_read on public.security_guardrail_events for select to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','compliance'));
create policy plan2_events_insert on public.security_guardrail_events for insert to finbrain_app, finbrain_worker
  with check (tenant_id = public.finbrain_tenant_id());
create policy plan2_owner_disclosure_chain on public.audit_log for select to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director');
create policy plan2_owner_workflow_chain on public.workflow_audit_log for select to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() = 'owner_director');
-- Employee record vocabulary is shared with the disclosure service. This grants
-- HR ciphertext only for employee data; it never widens customer/card disclosure.
create policy plan2_employee_vault on public.token_vault for select to finbrain_app
  using (tenant_id = public.finbrain_tenant_id()
    and entity_type in ('PERSON','AMOUNT','NRIC','BANKACC','EMAIL','PHONE','ADDR')
    and (public.finbrain_role() = 'owner_director' or exists (
      select 1 from public.user_roles r where r.tenant_id = public.finbrain_tenant_id()
        and r.user_id = public.finbrain_user_id() and r.active and r.job_functions ? 'hr'))
    and data_class = 'employee_personal');
grant select on public.agent_security_controls to finbrain_app, finbrain_worker;
grant insert, update on public.agent_security_controls to finbrain_app;
create policy plan2_controls_read on public.agent_security_controls for select to finbrain_app, finbrain_worker
  using (tenant_id = public.finbrain_tenant_id());
create policy plan2_controls_insert on public.agent_security_controls for insert to finbrain_app
  with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','compliance'));
create policy plan2_controls_update on public.agent_security_controls for update to finbrain_app
  using (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','compliance'))
  with check (tenant_id = public.finbrain_tenant_id() and public.finbrain_role() in ('owner_director','compliance'));
grant select, insert, update on public.agent_budget_windows to finbrain_app, finbrain_worker;
create policy plan2_budgets on public.agent_budget_windows to finbrain_app, finbrain_worker
  using (tenant_id = public.finbrain_tenant_id()) with check (tenant_id = public.finbrain_tenant_id());

-- Database safety net supplements the application lock and check.
create function public.plan2_protect_last_owner() returns trigger language plpgsql
set search_path = '' as $$ begin
  perform pg_advisory_xact_lock(hashtext('plan2:' || old.tenant_id::text));
  if old.active and old.user_role = 'owner_director'
    and (not new.active or new.user_role <> 'owner_director')
    and not exists (select 1 from public.user_roles r where r.tenant_id = old.tenant_id
      and r.user_id <> old.user_id and r.active and r.user_role = 'owner_director') then
    raise exception 'last_owner_required';
  end if;
  return new;
end $$;
create trigger plan2_last_owner before update on public.user_roles
  for each row execute function public.plan2_protect_last_owner();

create function public.plan2_settings_tighten() returns trigger language plpgsql
set search_path = '' as $$ begin
  if (new.document #>> '{security,session_idle_minutes}')::integer >
       (old.document #>> '{security,session_idle_minutes}')::integer
    or not (new.document #> '{security,mfa_required_roles}') @>
       (old.document #> '{security,mfa_required_roles}') then
    raise exception 'security_may_only_tighten';
  end if;
  if new.version <> old.version + 1 then raise exception 'settings_version_conflict'; end if;
  return new;
end $$;
create trigger plan2_settings_tighten before update on public.tenant_settings
  for each row execute function public.plan2_settings_tighten();
