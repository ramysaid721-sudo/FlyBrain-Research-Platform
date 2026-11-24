create index if not exists flybrain_agent_events_task_idx
  on private.flybrain_agent_events (task_id, occurred_at, event_id)
  where task_id is not null;
