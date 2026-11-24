create or replace function private.flybrain_eec_ledger_secret(p_name text)
returns text
language plpgsql
security invoker
set search_path = pg_catalog, vault
as $$
declare v_secret text;
begin
  if p_name <> 'flybrain_eec_ledger_token' then
    raise exception 'secret_name_not_allowed';
  end if;
  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name = 'flybrain_eec_ledger_token';
  if v_secret is null or length(v_secret) < 32 then
    raise exception 'eec_ledger_secret_unavailable';
  end if;
  return v_secret;
end;
$$;

revoke all on function private.flybrain_eec_ledger_secret(text) from public, anon, authenticated;
grant execute on function private.flybrain_eec_ledger_secret(text) to service_role;

create or replace function public.flybrain_eec_ledger_secret(p_name text)
returns text
language sql
security invoker
set search_path = pg_catalog, private
as $$
  select private.flybrain_eec_ledger_secret(p_name);
$$;

revoke all on function public.flybrain_eec_ledger_secret(text) from public, anon, authenticated;
grant execute on function public.flybrain_eec_ledger_secret(text) to service_role;
