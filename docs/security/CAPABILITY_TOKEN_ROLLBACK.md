# Capability-token emergency rollback — Staging only

**WARNING:** This rollback restores UUID-only status RPCs and deliberately reopens the access-control weakness fixed by the forward migration. Never apply it to Production.

1. Restore the exact pre-change MCP Edge Function v26 source first.
2. Apply the complete SQL script at [supabase/rollback/20261120_revert_capability_tokens.sql](../../supabase/rollback/20261120_revert_capability_tokens.sql) to Staging only.
3. Verify that only the legacy function signatures exist and that execute privileges remain restricted to service_role.
4. Verify MCP initialize, tools/list, task submission, and status operations.
5. Do not promote the rolled-back state.

The rollback script restores the prior function bodies and grants, not merely the schema columns. It also removes the capability-token columns, so capability hashes are discarded. Use only as an emergency paired rollback of both database and Edge Function versions.
