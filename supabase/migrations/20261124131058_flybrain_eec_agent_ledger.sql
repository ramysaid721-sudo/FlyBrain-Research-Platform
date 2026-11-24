create table if not exists private.flybrain_agent_runs (
  run_id uuid primary key,
  plan_id uuid not null unique,
  plan_sha256 text not null check (plan_sha256 ~ '^[0-9a-f]{64}$'),
  objective_sha256 text not null check (objective_sha256 ~ '^[0-9a-f]{64}$'),
  task_kind text not null check (task_kind in ('general','research','engineering','security','performance','documentation')),
  data_classification text not null default 'internal'
    check (data_classification in ('public','internal','confidential','prohibited')),
  status text not null default 'planned'
    check (status in ('planned','queued','running','reviewing','completed','failed','cancelled','policy_denied')),
  max_parallel_tasks integer not null default 3 check (max_parallel_tasks between 1 and 4),
  max_spend_usd numeric(12,8) not null default 0 check (max_spend_usd = 0),
  external_data_transfer boolean not null default false check (external_data_transfer = false),
  policy_snapshot jsonb not null default '{}'::jsonb check (jsonb_typeof(policy_snapshot) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists private.flybrain_agent_tasks (
  task_id uuid primary key,
  run_id uuid not null references private.flybrain_agent_runs(run_id) on delete cascade,
  task_key text not null,
  role text not null check (role in (
    'strategic_planner','research_specialist','systems_architect','software_engineer',
    'security_reviewer','qa_verifier','code_reviewer','performance_optimizer',
    'documentation_specialist','synthesizer'
  )),
  task_type text not null,
  status text not null default 'planned'
    check (status in ('planned','queued','ready','running','completed','failed','timed_out',
                      'reviewed','accepted','rejected','policy_denied','retry_queued')),
  depends_on uuid[] not null default '{}'::uuid[],
  input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  output_sha256 text check (output_sha256 is null or output_sha256 ~ '^[0-9a-f]{64}$'),
  provider_id text,
  model_id text,
  attempt_count integer not null default 0 check (attempt_count between 0 and 10),
  idempotency_key text not null unique,
  lease_token uuid,
  lease_expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (run_id, task_key)
);

create table if not exists private.flybrain_agent_attempts (
  attempt_id uuid primary key,
  task_id uuid not null references private.flybrain_agent_tasks(task_id) on delete cascade,
  attempt_number integer not null check (attempt_number between 1 and 10),
  provider_id text,
  model_id text,
  status text not null check (status in ('started','completed','failed','timed_out','policy_denied','cancelled')),
  input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  output_sha256 text check (output_sha256 is null or output_sha256 ~ '^[0-9a-f]{64}$'),
  cost_usd numeric(12,8) not null default 0 check (cost_usd = 0),
  external_data_transfer boolean not null default false check (external_data_transfer = false),
  error_code text check (error_code is null or length(error_code) <= 100),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  unique (task_id, attempt_number)
);

create table if not exists private.flybrain_agent_events (
  event_id bigint generated always as identity primary key,
  run_id uuid not null references private.flybrain_agent_runs(run_id) on delete cascade,
  task_id uuid references private.flybrain_agent_tasks(task_id) on delete cascade,
  event_type text not null check (event_type in (
    'run_created','task_planned','task_queued','task_claimed','task_started',
    'task_completed','task_failed','task_retried','task_reviewed','task_accepted',
    'task_rejected','policy_denied','run_completed','run_failed','run_cancelled'
  )),
  from_status text,
  to_status text,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  occurred_at timestamptz not null default now()
);

create index if not exists flybrain_agent_runs_status_created_idx
  on private.flybrain_agent_runs (status, created_at desc);
create index if not exists flybrain_agent_tasks_run_status_idx
  on private.flybrain_agent_tasks (run_id, status, created_at);
create index if not exists flybrain_agent_tasks_ready_idx
  on private.flybrain_agent_tasks (status, created_at)
  where status in ('queued','ready','retry_queued');
create index if not exists flybrain_agent_attempts_task_idx
  on private.flybrain_agent_attempts (task_id, attempt_number desc);
create index if not exists flybrain_agent_events_run_idx
  on private.flybrain_agent_events (run_id, occurred_at, event_id);

alter table private.flybrain_agent_runs enable row level security;
alter table private.flybrain_agent_tasks enable row level security;
alter table private.flybrain_agent_attempts enable row level security;
alter table private.flybrain_agent_events enable row level security;

revoke all on table private.flybrain_agent_runs,
  private.flybrain_agent_tasks,
  private.flybrain_agent_attempts,
  private.flybrain_agent_events from public, anon, authenticated;

grant usage on schema private to service_role;
grant select, insert, update, delete on table private.flybrain_agent_runs,
  private.flybrain_agent_tasks, private.flybrain_agent_attempts to service_role;
grant select, insert on table private.flybrain_agent_events to service_role;
grant usage, select on sequence private.flybrain_agent_events_event_id_seq to service_role;

comment on table private.flybrain_agent_runs is
  'Private EEC orchestration run ledger. Stores hashes and policy metadata, never raw objectives or secrets.';
comment on table private.flybrain_agent_tasks is
  'Private EEC task ledger with bounded roles, dependency IDs, idempotency, and fenced leases.';
comment on table private.flybrain_agent_attempts is
  'Private append-oriented agent attempt metadata; spend and external transfer are constrained to zero/false.';
comment on table private.flybrain_agent_events is
  'Private append-only EEC event history. Metadata must be sanitized and contain no prompts or credentials.';
