# Capability-token emergency rollback — Staging only

WARNING: This rollback deliberately restores UUID-only status RPCs and reopens the access-control weakness. Never apply it to Production. Use only if the Staging release is unusable.

1. Restore the exact pre-change MCP Edge Function source v26 first.
2. Apply the SQL below in Staging only.
3. Verify the restored function signatures and grants, then verify MCP health.
4. Do not promote the rolled-back state.

```sql
DROP FUNCTION IF EXISTS public.flybrain_task_group_status(uuid,text);
DROP FUNCTION IF EXISTS public.flybrain_task_status(uuid,text);
DROP FUNCTION IF EXISTS public.flybrain_enqueue_task_group(jsonb,text,text,text);
DROP FUNCTION IF EXISTS public.flybrain_enqueue_task(text,jsonb,text,text);
ALTER TABLE public.flybrain_task_runs DROP CONSTRAINT IF EXISTS flybrain_task_runs_access_token_hash_format, DROP COLUMN IF EXISTS access_token_hash;
ALTER TABLE private.flybrain_task_groups DROP CONSTRAINT IF EXISTS flybrain_task_groups_access_token_hash_format, DROP COLUMN IF EXISTS access_token_hash;

-- Recreate the four legacy function definitions and grants from the pre-change
-- migration/deployment snapshot before reopening MCP. Do not leave MCP v26 offline.
```

The database and deployed MCP sources are preserved on the dedicated branch, so rollback inputs are recoverable. This rollback is intentionally gated because restoring UUID-only access weakens security.