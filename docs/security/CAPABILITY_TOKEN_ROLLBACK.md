# Capability-token rollback — Staging only

The capability-token migration replaces UUID-only task and group status RPCs. Rolling it back deliberately reopens the prior access-control weakness. Never apply a rollback to Production.

## Current rollback readiness

**Do not execute a rollback from this document yet.** The original pre-capability SQL definitions for all four RPCs are not included in this branch's migration history. The old MCP v26 source is preserved on the separate recovery branch, but that source alone does not reconstruct the exact database function bodies and grants.

Before rollback, recover and review the exact pre-change definitions for:
- `public.flybrain_enqueue_task(text,jsonb,text)`
- `public.flybrain_enqueue_task_group(jsonb,text,text)`
- `public.flybrain_task_status(uuid)`
- `public.flybrain_task_group_status(uuid)`

Use a verified pre-change database/schema snapshot or archived migration source. Then prepare one atomic Staging-only rollback that:
1. Restores those exact function definitions and grants.
2. Restores the matching MCP v26 source.
3. Drops the capability-token overloads and hash columns only after the restored functions are verified.
4. Runs MCP health, task submission, and status smoke tests.
5. Confirms the project remains Staging.

Do not drop the hash columns or restore UUID-only access until all four legacy function definitions and grants have been recovered and reviewed. The existing token-protected Staging state is the safer operating state.
