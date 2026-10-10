-- Customer email addresses and phone numbers stay masked for general employees.
-- New vault rows no longer list the role (app/security/tokenize.py ACL_POLICY), and
-- the application checks the current policy on every read. This removes the role
-- from rows written under the older policy, so row-level security agrees too.
begin;

update public.token_vault
set allowed_roles = allowed_roles - 'general_employee'
where entity_type in ('EMAIL', 'PHONE')
  and allowed_roles ? 'general_employee';

commit;
