# FlyBrain Scheduled Continuity Qualification — 2026-11-20

## Outcome

**Scheduled lease recovery passed.** The second execution was dispatched by Supabase Cron without a ChatGPT tool call initiating it.

## Test sequence

1. Updated the staging worker allowlist and deterministic handler for task `d3000000-0000-4000-8000-000000000008`.
2. Corrected the Supabase Vault trigger URL to the latest READY Vercel staging deployment.
3. Temporarily set the staging cron interval to every minute and the test lease to 30 seconds to shorten the qualification window.
4. A first dispatch started execution `3230ccc9-42dd-4a41-805f-576f15d575fa`, wrote `full-continuity-phase-1`, and intentionally stopped.
5. The next scheduled Supabase Cron run at 10:14:00 UTC dispatched execution `8c0f3eed-947a-4cc4-9c56-e2a336a8f680`.
6. The second execution loaded the phase-1 checkpoint, recorded `full-continuity-phase-2`, referenced the prior execution ID, and completed successfully.
7. Independent inspection confirmed both execution records and both checkpoints in Supabase.
8. The cron schedule was restored to `*/5 * * * *`, with the normal 300-second default lease.

## Evidence

- Supabase cron job: `flybrain-worker-dispatch-every-five-minutes`, job ID 3.
- Cron execution at 10:14:00 UTC: succeeded.
- pg_net HTTP response ID 22: HTTP 200, no timeout.
- Phase-1 execution: `3230ccc9-42dd-4a41-805f-576f15d575fa`.
- Phase-2 execution: `8c0f3eed-947a-4cc4-9c56-e2a336a8f680`, status succeeded.
- Task `d3000000-0000-4000-8000-000000000008`: VERIFIED.
- Vercel deployment used: staging Preview only; production deployment was not changed.

## Scope and limitation

This proves the scheduled control plane can recover an expired worker lease and resume from a durable checkpoint without a new ChatGPT tool call. The ChatGPT conversation remained open during this test; a literal test with the conversation closed and a scheduler process restart was not performed. Do not interpret this result as proof that every task handler or every cloud provider is production-qualified.
