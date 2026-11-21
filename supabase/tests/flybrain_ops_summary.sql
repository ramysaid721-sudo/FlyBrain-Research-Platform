-- Run after the flybrain_ops_summary migration has been applied.
-- All assertions execute inside a transaction and are rolled back.
begin;

do $test$
declare
  summary jsonb;
begin
  summary := public.flybrain_ops_summary();

  if jsonb_typeof(summary) <> 'object' then
    raise exception 'summary must be a JSON object';
  end if;

  if not (summary ?& array[
    'generated_at', 'environment', 'queue', 'tasks',
    'latency_seconds', 'leases', 'events', 'event_coverage',
    'groups', 'cron'
  ]) then
    raise exception 'summary is missing required aggregate sections';
  end if;

  if summary ?| array[
    'task_id', 'group_id', 'payload', 'result',
    'access_token_hash', 'capability_token', 'command',
    'query', 'authorization', 'service_role'
  ] then
    raise exception 'summary contains a prohibited top-level field';
  end if;

  if has_function_privilege('anon', 'public.flybrain_ops_summary()', 'EXECUTE')
     or has_function_privilege('authenticated', 'public.flybrain_ops_summary()', 'EXECUTE') then
    raise exception 'public or authenticated roles must not execute the summary RPC';
  end if;

  if not has_function_privilege('service_role', 'public.flybrain_ops_summary()', 'EXECUTE') then
    raise exception 'service_role must be able to execute the summary RPC';
  end if;
end;
$test$;

rollback;
