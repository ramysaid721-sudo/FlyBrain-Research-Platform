# FlyBrain Task Queue Observability Runbook

**Scope:** Supabase Staging project only. These queries are read-only and are intended for operational checks. Do not run them against Production without a separate change plan.

## 1. Queue depth and visibility

```sql
select *
from pgmq.metrics('flybrain_tasks');
```

Interpretation:
- `queue_length` is the current queue backlog.
- `queue_visible_length` is the currently visible backlog.
- `total_messages` is cumulative message accounting and is not the same as pending backlog.

## 2. Task ledger by state

```sql
select
  status,
  count(*) as task_count,
  round(avg(attempts)::numeric, 2) as avg_attempts
from public.flybrain_task_runs
group by status
order by status;
```

## 3. Execution latency

```sql
select
  count(*) as completed_tasks,
  round(avg(extract(epoch from (completed_at - created_at)))::numeric, 2) as avg_seconds,
  percentile_cont(0.5) within group (
    order by extract(epoch from (completed_at - created_at))
  ) as median_seconds,
  percentile_cont(0.95) within group (
    order by extract(epoch from (completed_at - created_at))
  ) as p95_seconds,
  max(extract(epoch from (completed_at - created_at))) as max_seconds
from public.flybrain_task_runs
where status = 'completed'
  and completed_at is not null;
```

This measures end-to-end elapsed time from task creation to completion. It is not a pure worker execution-time metric: it includes queue wait and provider latency.

## 4. Event telemetry

```sql
select
  event_type,
  count(*) as event_count,
  min(occurred_at) as first_seen,
  max(occurred_at) as last_seen
from private.flybrain_task_events
group by event_type
order by event_type;
```

Compare task rows with their event history:

```sql
select
  t.status,
  count(*) as tasks,
  count(*) filter (where e.event_id is null) as tasks_without_events
from public.flybrain_task_runs t
left join private.flybrain_task_events e on e.task_id = t.task_id
group by t.status
order by t.status;
```

Historical note: event telemetry was introduced after the first Staging queue tasks. A task created before the first `enqueued` event is not automatically evidence of a logging failure. Compare its `created_at` with the earliest event timestamp before classifying it as a gap.

## 5. Lease health

```sql
select
  count(*) filter (
    where status = 'running' and lease_expires_at > now()
  ) as active_leases,
  count(*) filter (
    where status = 'running'
      and (lease_expires_at is null or lease_expires_at <= now())
  ) as expired_leases
from public.flybrain_task_runs;
```

An expired lease requires investigation. Do not manually reset task state without checking the claim token, queue message, and worker retry policy.

## 6. Group integrity and capability-token hash alignment

```sql
select
  count(*) as total_groups,
  coalesce(sum(expected_tasks), 0) as expected_children,
  (select count(*) from private.flybrain_task_group_items) as linked_children,
  (
    select count(*)
    from private.flybrain_task_groups g
    where not exists (
      select 1
      from private.flybrain_task_group_items i
      where i.group_id = g.group_id
    )
  ) as groups_without_items
from private.flybrain_task_groups;
```

```sql
select count(*) as capability_hash_mismatches
from public.flybrain_task_runs t
join private.flybrain_task_group_items i on i.task_id = t.task_id
join private.flybrain_task_groups g on g.group_id = i.group_id
where t.access_token_hash is distinct from g.access_token_hash;
```

Expected mismatch count: zero.

## 7. Cron worker schedule

```sql
select jobid, jobname, schedule, active
from cron.job
where jobname = 'flybrain-task-worker-every-minute';
```

The worker job should remain active with the intended one-minute schedule. Do not select or print the job command in routine diagnostics because it contains the worker credential reference.

## 8. Staging baseline observed on 2026-11-20 (UTC)

| Metric | Observed value |
|---|---:|
| Completed tasks | 25 |
| Failed tasks | 2 |
| Queue length | 0 |
| Visible queue length | 0 |
| Active leases | 0 |
| Expired leases | 0 |
| Task groups | 7 |
| Expected / linked group children | 11 / 11 |
| Capability hash mismatches | 0 |
| Average end-to-end completion time | 26.82 s |
| Median end-to-end completion time | 24.42 s |
| P95 end-to-end completion time | 55.00 s |
| Maximum end-to-end completion time | 145.44 s |

The two historical failed rows had the explicit marker `synthetic_test_cleaned_up`; they were prior synthetic test artifacts, not current provider failures. Eight earliest tasks predated event instrumentation and have no event rows. Later event telemetry is consistent with task status, including retry events.

## 9. Security and data-handling notes

- Do not include task payloads, query text, results, capability tokens, worker tokens, or authorization headers in dashboards or logs.
- Capability tokens are returned to the submitter once; the database stores only SHA-256 hashes.
- The Crossref query-screening helper blocks known credential and personal-data patterns. It is not a general-purpose DLP system and cannot identify every unpublished or confidential research passage.
- The `data_classification = public` flag is a caller assertion, not an independent proof of public status.
- Private-schema RLS linter INFO notices are not a reason to add permissive policies. Preserve the current restricted grants and review actual role access before changing policies.
- All checks in this runbook are read-only. Any repair, schema change, retry, archive deletion, or Production operation requires a separate reviewed action.


## 10. Worker HTTP response semantics

The current worker intentionally distinguishes authentication/infrastructure failures from task-level failures:

| HTTP status | Meaning |
|---:|---|
| 200 | Worker idle or task completed |
| 202 | Crossref rate-limited; task deferred for retry |
| 401 | Missing or incorrect worker capability secret |
| 409 | Claim/completion/failure state conflict |
| 502 | Task execution failed and the ledger was updated as failed or requeued |
| 503 | Worker configuration, queue, or task-state update unavailable |

A 502 with `status = failed_or_requeued` does not by itself mean the worker process crashed. Inspect the returned `error_code` and task ledger state. For example, the direct defense-in-depth test against a synthetic sensitive task produced `query_blocked_by_external_data_safety_policy`, marked the task failed, and did not send the query to Crossref.

## 11. Cron and queue health spot-check (2026-11-20 UTC)

- The 12 most recent recorded Cron runs were all `succeeded`.
- The worker schedule remained active at once per minute.
- Queue metrics reported `queue_length = 0` and `queue_visible_length = 0`.
- The task ledger had 25 completed and 2 historical synthetic-test failures.
- There were zero queued or running tasks and zero expired leases.
- The no-token worker POST returned HTTP 401; the associated temporary HTTP response row was removed after inspection.

Cron success means the scheduled SQL command executed successfully; it does not alone prove that an actual task was completed. Pair Cron history with queue depth and task-ledger state.

## 12. Saved Supabase Staging operations notebook

A read-only Supabase notebook containing the queue-depth, task-state/retry, end-to-end latency, lease-health, event-telemetry, group-integrity/token-hash alignment, and Cron-schedule queries is available in the Staging project:

- Notebook: [FlyBrain Staging Operations](https://supabase.com/dashboard/project/iudimypauqbkyvjuprgp/explorer/notebook/668c1c64-2cc3-4307-82a1-6ba9d0bcfdb0)
- Notebook ID: `668c1c64-2cc3-4307-82a1-6ba9d0bcfdb0`
- All seven query cells were executed successfully on 2026-11-20 UTC.
- The notebook contains SELECT-only SQL and does not display task payloads, results, query text, or credentials.

## 13. Enhanced Staging operations notebook (v2)

The enhanced read-only notebook adds task event coverage, Cron run reliability, and the last 20 Cron execution durations. All ten database query cells executed successfully.

- Notebook: [FlyBrain Staging Operations v2](https://supabase.com/dashboard/project/iudimypauqbkyvjuprgp/explorer/notebook/0375b305-88ac-49b9-b29c-f93c7a8cb45f)
- Notebook ID: `0375b305-88ac-49b9-b29c-f93c7a8cb45f`
- Latest observed Cron run: succeeded; duration approximately 0.015 seconds.
- 262 Cron runs were recorded as succeeded at the time of this check; no unsuccessful runs were present in the returned aggregate.
- Eight completed tasks predate event instrumentation and have no event rows; this is documented as historical coverage, not treated as current logging failure.
- Cron queries deliberately omit the job command and return message to avoid disclosing operational configuration.
