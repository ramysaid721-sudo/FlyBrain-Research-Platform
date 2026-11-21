-- Owner-gated operational aggregate RPC.
-- The Edge Function verifies a Supabase Auth user JWT and an explicit owner UUID
-- allowlist before calling this function. This RPC is additionally restricted
-- to service_role so it cannot be called directly by anon/authenticated clients.
-- It returns aggregate metadata only; never task payloads, results, IDs, or tokens.

create or replace function public.flybrain_ops_summary()
returns jsonb
language sql
security definer
set search_path = pg_catalog
as $function$
  select jsonb_build_object(
    'generated_at', now(),
    'environment', 'supabase-staging',
    'queue', (
      select jsonb_build_object(
        'queue_name', m.queue_name,
        'queue_length', m.queue_length,
        'visible_length', m.queue_visible_length,
        'total_messages', m.total_messages,
        'newest_message_age_seconds', m.newest_msg_age_sec,
        'oldest_message_age_seconds', m.oldest_msg_age_sec,
        'scrape_time', m.scrape_time
      )
      from pgmq.metrics('flybrain_tasks') as m
      limit 1
    ),
    'tasks', jsonb_build_object(
      'by_status', coalesce((
        select jsonb_object_agg(s.status, s.task_count)
        from (
          select status, count(*) as task_count
          from public.flybrain_task_runs
          group by status
        ) as s
      ), '{}'::jsonb),
      'completed_average_attempts', (
        select round(avg(attempts)::numeric, 2)
        from public.flybrain_task_runs
        where status = 'completed'
      ),
      'completed_max_attempts', (
        select max(attempts)
        from public.flybrain_task_runs
        where status = 'completed'
      )
    ),
    'latency_seconds', (
      select jsonb_build_object(
        'completed_count', count(*),
        'average', round(avg(extract(epoch from (completed_at - created_at)))::numeric, 2),
        'median', round((percentile_cont(0.5) within group (
          order by extract(epoch from (completed_at - created_at))
        ))::numeric, 2),
        'p95', round((percentile_cont(0.95) within group (
          order by extract(epoch from (completed_at - created_at))
        ))::numeric, 2),
        'maximum', round(max(extract(epoch from (completed_at - created_at)))::numeric, 2)
      )
      from public.flybrain_task_runs
      where status = 'completed' and completed_at is not null
    ),
    'leases', (
      select jsonb_build_object(
        'active', count(*) filter (
          where status = 'running' and lease_expires_at > now()
        ),
        'expired', count(*) filter (
          where status = 'running' and lease_expires_at <= now()
        )
      )
      from public.flybrain_task_runs
    ),
    'events', (
      select coalesce(jsonb_object_agg(e.event_type, e.event_count), '{}'::jsonb)
      from (
        select event_type, count(*) as event_count
        from private.flybrain_task_events
        group by event_type
      ) as e
    ),
    'event_coverage', (
      select jsonb_build_object(
        'completed_without_events', count(*) filter (
          where t.status = 'completed' and e.task_id is null
        ),
        'failed_without_events', count(*) filter (
          where t.status = 'failed' and e.task_id is null
        )
      )
      from public.flybrain_task_runs as t
      left join (
        select distinct task_id
        from private.flybrain_task_events
      ) as e on e.task_id = t.task_id
    ),
    'groups', jsonb_build_object(
      'group_count', (
        select count(*) from private.flybrain_task_groups
      ),
      'expected_tasks', (
        select coalesce(sum(expected_tasks), 0)
        from private.flybrain_task_groups
      ),
      'linked_tasks', (
        select count(*) from private.flybrain_task_group_items
      ),
      'empty_groups', (
        select count(*)
        from private.flybrain_task_groups as g
        where not exists (
          select 1 from private.flybrain_task_group_items as i
          where i.group_id = g.group_id
        )
      ),
      'capability_hash_mismatches', (
        select count(*)
        from private.flybrain_task_group_items as gi
        join private.flybrain_task_groups as gg on gg.group_id = gi.group_id
        join public.flybrain_task_runs as tr on tr.task_id = gi.task_id
        where gg.access_token_hash is distinct from tr.access_token_hash
      )
    ),
    'cron', (
      select jsonb_build_object(
        'job_id', j.jobid,
        'job_name', j.jobname,
        'schedule', j.schedule,
        'active', j.active,
        'last_24h_runs', (
          select count(*)
          from cron.job_run_details as r
          where r.jobid = j.jobid and r.start_time >= now() - interval '24 hours'
        ),
        'last_24h_succeeded', (
          select count(*)
          from cron.job_run_details as r
          where r.jobid = j.jobid and r.start_time >= now() - interval '24 hours'
            and r.status = 'succeeded'
        ),
        'last_24h_failed', (
          select count(*)
          from cron.job_run_details as r
          where r.jobid = j.jobid and r.start_time >= now() - interval '24 hours'
            and r.status <> 'succeeded'
        ),
        'latest_run', (
          select jsonb_build_object(
            'status', r.status,
            'started_at', r.start_time,
            'ended_at', r.end_time,
            'duration_ms', case when r.end_time is not null
              then round((extract(epoch from (r.end_time - r.start_time)) * 1000)::numeric, 2)
              else null end
          )
          from cron.job_run_details as r
          where r.jobid = j.jobid
          order by r.start_time desc
          limit 1
        )
      )
      from cron.job as j
      where j.jobname = 'flybrain-task-worker-every-minute'
      order by j.jobid desc
      limit 1
    )
  );
$function$;

revoke all on function public.flybrain_ops_summary() from public;
revoke all on function public.flybrain_ops_summary() from anon;
revoke all on function public.flybrain_ops_summary() from authenticated;
grant execute on function public.flybrain_ops_summary() to service_role;
