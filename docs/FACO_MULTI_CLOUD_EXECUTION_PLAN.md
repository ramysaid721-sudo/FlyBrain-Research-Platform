# FACO — FlyBrain Adaptive Compute Orchestrator

Status: staging implementation in progress. This document distinguishes verified behavior from planned provider integrations.

## Objective

Reduce mission completion time by scheduling independent, bounded tasks concurrently across compute services the account is authorized to use. Supabase remains the durable source of truth. Workers are replaceable; no task state may exist only in a ChatGPT session or an ephemeral worker.

## Current topology

- **Control plane — Supabase:** task ledger, dependencies, leases, checkpoints, evidence, audit records, and pg_cron dispatch.
- **Worker plane — Vercel Sandbox:** isolated Python worker. The named staging sandbox is persistent by snapshot, but individual sessions are stopped after bounded work. One sandbox is currently used; no unverified worker pool is created.
- **CI/test plane — GitHub Actions:** a three-shard matrix has been committed to the staging workflow. GitHub created all three matrix jobs, but the latest run failed before any step because every job reported runner_id=0, an empty runner_name, and zero steps. This is a GitHub-hosted runner allocation failure, not a pytest result.
- **Fallback test plane — Vercel Sandbox:** the same three test shards were run concurrently in the existing 1-vCPU staging sandbox. Results: 35 + 22 + 17 = 74 passed, zero failures, on Python 3.14.4. Python 3.12 compatibility remains unverified.
- **Supervisory plane — ChatGPT:** planning, review, and exception handling only. It is not the scheduler or durable task store.

## Verified operational facts (2026-11-20)

1. Supabase Cron job `flybrain-worker-dispatch-every-five-minutes` is active with schedule `*/5 * * * *`.
2. pg_cron recorded successful runs at 09:55, 10:00, and 10:05 UTC. Corresponding pg_net dispatches returned HTTP 204 when no supported task was eligible. This confirms the scheduler-to-dispatch path runs independently of a conversational tool call.
3. The checkpoint/idempotency qualification task completed a two-execution recovery test. The first worker saved phase 1 and stopped; after lease expiry, a later worker resumed from that checkpoint. Independent ledger inspection found phase 2, a successful execution, and exactly one side-effect row for the idempotency key. The task is VERIFIED.
4. The full-continuity qualification task completed its two-phase scheduled recovery test and is VERIFIED. The first execution saved phase 1 and stopped; after its 30-second lease expired, Supabase Cron automatically dispatched a second execution, which resumed from phase 1 and saved phase 2. The second dispatch was not initiated by a ChatGPT tool call. The ChatGPT conversation itself was not closed, so a literal closed-session test remains a separate follow-up.
5. The latest Vercel preview for the staging branch is READY at commit `420d2b6`. Production was not modified.

## Provider inventory and constraints

| Provider | Current account evidence | Policy |
|---|---|---|
| Supabase | Existing Free project; active Cron and Edge Function | Use for orchestration and durable state, not heavy compute |
| Vercel | Existing staging project and one reusable Sandbox | Use bounded single-worker execution until free concurrency/quota is confirmed |
| GitHub Actions | Three-shard matrix committed; hosted runner allocation currently failing before steps | Retry only as quota permits; do not interpret runner allocation errors as test failures |
| Railway | Connector is available, but the account currently has zero projects | Do not create a project until plan/quota and user workspace are confirmed |
| Render | A workspace is visible, but no workspace has been selected for operations | Do not create or alter services without explicit workspace confirmation |
| Cloudflare | No Cloudflare connector is currently available in this execution environment | Do not claim it is connected; revisit if an authorized connection becomes available |
| TinyFish | Wallet balance is -$0.44 and auto-reload is unconfigured | Disabled for this mission; no top-up or paid run |

## Scheduling and concurrency policy

- Start with three independent CI shards, maximum parallelism three.
- Keep task claims transactional and protected by leases.
- Only tasks with registered handlers and satisfied dependencies may be claimed.
- Do not create multiple Vercel sandboxes until free concurrency and quota are confirmed.
- Prefer provider-native parallel jobs over repeated polling or repeatedly starting fresh compute.
- Stop or snapshot workers immediately after their bounded task.
- Use deterministic retries, exponential backoff, idempotency keys, and independent verification.
- Record provider, runtime, commit, test shard, start/end times, and evidence for every execution.

## Next engineering steps

1. Complete the scheduled two-stage full-continuity task and independently verify its audit trail.
2. Resolve GitHub-hosted runner allocation by a bounded retry or use the Vercel fallback without overstating Python 3.12 compatibility.
3. Add a provider adapter interface and quota-aware worker selection before adding any new cloud provider.
4. Connect additional providers only after confirming authorized account access, free-tier limits, and safe secret handling.
5. Keep model-backed reasoning blocked until an approved endpoint and explicit spending/data policy exist.

## Non-goals and safety boundaries

- No use of third-party or public compute without explicit authorization.
- No account creation, paid upgrades, wallet top-ups, overage, or credit-card enrollment.
- No production deployment or destructive operation.
- No embedding of permanent secrets in source code or logs.
- No external model processing of confidential project data without approval.
