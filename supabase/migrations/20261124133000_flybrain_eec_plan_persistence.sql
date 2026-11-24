-- EEC durable plan persistence for the existing FlyBrain Staging ledger.
-- No raw objective, prompt, provider credential, or task output is stored here.

create table if not exists private.flybrain_agent_artifacts (
  artifact_id uuid primary key,
  run_id uuid not null references private.flybrain_agent_runs(run_id),
  task_id uuid not null references private.flybrain_agent_tasks(task_id),
  artifact_type text not null check (artifact_type in ('finding','review','test_result','synthesis','evidence_manifest')),
  content jsonb not null check (jsonb_typeof(content) = 'object'),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  data_classification text not null check (data_classification in ('public','internal','confidential')),
  created_at timestamptz not null default now(),
  unique (task_id, artifact_type)
);

create index if not exists flybrain_agent_artifacts_run_idx
  on private.flybrain_agent_artifacts (run_id, created_at desc);

alter table private.flybrain_agent_artifacts enable row level security;
revoke all on table private.flybrain_agent_artifacts from public, anon, authenticated;
grant usage on schema private to service_role;
grant select, insert on table private.flybrain_agent_artifacts to service_role;
revoke update, delete on table private.flybrain_agent_artifacts from service_role;

create or replace function private.flybrain_validate_agent_dependencies()
returns trigger
language plpgsql
set search_path = pg_catalog, private
as $$
declare dependency_id uuid;
begin
  foreach dependency_id in array new.depends_on loop
    if dependency_id = new.task_id then
      raise exception 'agent task cannot depend on itself';
    end if;
    if not exists (
      select 1 from private.flybrain_agent_tasks t
      where t.task_id = dependency_id and t.run_id = new.run_id
    ) then
      raise exception 'agent dependency must reference a task in the same run';
    end if;
  end loop;
  return new;
end;
$$;

drop trigger if exists flybrain_validate_agent_dependencies on private.flybrain_agent_tasks;
create constraint trigger flybrain_validate_agent_dependencies
after insert or update on private.flybrain_agent_tasks
deferrable initially deferred
for each row execute function private.flybrain_validate_agent_dependencies();

create or replace function public.flybrain_eec_persist_plan(p_plan jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, private
as $$
declare
  v_plan_id uuid;
  v_plan_sha text;
  v_objective_sha text;
  v_task_kind text;
  v_classification text;
  v_parallel integer;
  v_tasks jsonb;
  v_existing_sha text;
  v_count integer;
  v_task jsonb;
  v_task_id uuid;
  v_task_key text;
  v_role text;
  v_depends uuid[];
begin
  if jsonb_typeof(p_plan) <> 'object' then raise exception 'invalid_plan_object'; end if;
  v_plan_id := (p_plan->>'plan_id')::uuid;
  v_plan_sha := p_plan->>'plan_sha256';
  v_objective_sha := p_plan->>'objective_sha256';
  v_task_kind := p_plan->>'task_kind';
  v_classification := p_plan->>'data_classification';
  v_parallel := (p_plan->'policy'->>'max_parallel_tasks')::integer;
  v_tasks := p_plan->'tasks';

  if coalesce(p_plan->>'status','') <> 'planned'
     or coalesce(v_plan_sha,'') !~ '^[0-9a-f]{64}$'
     or coalesce(v_objective_sha,'') !~ '^[0-9a-f]{64}$'
     or coalesce(v_task_kind,'') not in ('general','research','engineering','security','performance','documentation')
     or coalesce(v_classification,'') not in ('public','internal','confidential')
     or coalesce(v_parallel,0) not between 1 and 4
     or coalesce(jsonb_typeof(v_tasks),'') <> 'array'
     or jsonb_array_length(coalesce(v_tasks,'[]'::jsonb)) < 1
     or jsonb_array_length(coalesce(v_tasks,'[]'::jsonb)) > 16 then
    raise exception 'plan_validation_failed';
  end if;

  if coalesce(p_plan->'policy'->>'max_spend','') <> '0'
     or coalesce(p_plan->'policy'->>'provider_calls_enabled','') <> 'false'
     or coalesce(p_plan->'policy'->>'external_data_transfer','') <> 'false'
     or coalesce(p_plan->'policy'->>'live_execution','') <> 'false'
     or coalesce(p_plan->'policy'->>'production_access','') <> 'false' then
    raise exception 'plan_policy_not_fail_closed';
  end if;

  select plan_sha256 into v_existing_sha
  from private.flybrain_agent_runs where plan_id = v_plan_id;
  if found then
    if v_existing_sha <> v_plan_sha then raise exception 'plan_id_conflict'; end if;
    select count(*) into v_count from private.flybrain_agent_tasks where run_id = v_plan_id;
    return jsonb_build_object('status','already_persisted','plan_id',v_plan_id,'task_count',v_count);
  end if;

  insert into private.flybrain_agent_runs (
    run_id, plan_id, plan_sha256, objective_sha256, task_kind,
    data_classification, status, max_parallel_tasks, max_spend_usd,
    external_data_transfer, policy_snapshot
  ) values (
    v_plan_id, v_plan_id, v_plan_sha, v_objective_sha, v_task_kind,
    v_classification, 'planned', v_parallel, 0, false,
    jsonb_build_object('eec_version',p_plan->>'eec_version',
      'max_parallel_tasks',v_parallel,'provider_calls_enabled',false,
      'external_data_transfer',false,'live_execution',false,'production_access',false)
  );

  for v_task in select value from jsonb_array_elements(v_tasks)
  loop
    v_task_id := (v_task->>'task_id')::uuid;
    v_task_key := v_task->>'task_type';
    v_role := v_task->>'role';
    if coalesce(v_role,'') not in (
      'strategic_planner','research_specialist','systems_architect','software_engineer',
      'security_reviewer','qa_verifier','code_reviewer','performance_optimizer',
      'documentation_specialist','synthesizer'
    ) or coalesce(v_task_key,'') = ''
      or coalesce(v_task->'input_ref'->>'objective_sha256','') <> v_objective_sha then
      raise exception 'invalid_agent_task';
    end if;

    select coalesce(array_agg(value::uuid), '{}'::uuid[]) into v_depends
    from jsonb_array_elements_text(coalesce(v_task->'depends_on','[]'::jsonb));

    insert into private.flybrain_agent_tasks (
      task_id,run_id,task_key,role,task_type,status,depends_on,input_sha256,idempotency_key
    ) values (
      v_task_id,v_plan_id,v_task_key,v_role,v_task_key,'planned',v_depends,
      v_objective_sha,v_plan_id::text || ':' || v_task_id::text
    );

    insert into private.flybrain_agent_events(run_id,task_id,event_type,to_status,metadata)
    values(v_plan_id,v_task_id,'task_planned','planned',jsonb_build_object('task_key',v_task_key,'role',v_role));
  end loop;

  select count(*) into v_count from private.flybrain_agent_tasks where run_id = v_plan_id;
  insert into private.flybrain_agent_events(run_id,event_type,to_status,metadata)
  values(v_plan_id,'run_created','planned',jsonb_build_object('task_count',v_count,'eec_version',p_plan->>'eec_version'));
  return jsonb_build_object('status','persisted','plan_id',v_plan_id,'task_count',v_count);
end;
$$;

revoke all on function public.flybrain_eec_persist_plan(jsonb) from public, anon, authenticated;
grant execute on function public.flybrain_eec_persist_plan(jsonb) to service_role;

create or replace function public.flybrain_eec_plan_status(p_plan_id uuid)
returns jsonb
language sql
security invoker
set search_path = pg_catalog, private
as $$
  select jsonb_build_object(
    'plan_id', r.plan_id,
    'status', r.status,
    'task_count', (select count(*) from private.flybrain_agent_tasks t where t.run_id = r.run_id),
    'task_status_counts', coalesce((
      select jsonb_object_agg(x.status,x.n)
      from (select status,count(*) as n from private.flybrain_agent_tasks where run_id=r.run_id group by status) x
    ), '{}'::jsonb),
    'created_at', r.created_at,
    'completed_at', r.completed_at
  )
  from private.flybrain_agent_runs r
  where r.plan_id = p_plan_id;
$$;

revoke all on function public.flybrain_eec_plan_status(uuid) from public, anon, authenticated;
grant execute on function public.flybrain_eec_plan_status(uuid) to service_role;
