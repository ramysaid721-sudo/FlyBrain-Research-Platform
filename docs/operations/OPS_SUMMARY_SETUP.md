# FlyBrain Operations Summary — Staging Setup

**Status:** source prepared; not deployed. The SQL migration has been syntax/runtime-tested inside a transaction and rolled back. No persistent database changes have been made.

## Authentication design

The endpoint uses Supabase Auth user JWT validation through the current `@supabase/server` Edge Function wrapper, then performs a second authorization check against a server-side allowlist of exact Supabase Auth user UUIDs.

The database RPC is `SECURITY DEFINER` but its EXECUTE privilege is revoked from `PUBLIC`, `anon`, and `authenticated`; only `service_role` can execute it. The Edge Function checks the user identity before invoking the RPC through its server-side admin client.

Never put a Supabase secret/service-role key in browser code, a Vercel `NEXT_PUBLIC_*` variable, or this repository.

## Required Staging function secrets

Set these in Supabase Dashboard → Project Settings / Edge Functions → Secrets for Staging only:

| Secret | Value |
|---|---|
| `FLYBRAIN_OPS_OWNER_IDS` | Comma-separated exact UUID(s) of explicitly authorized Supabase Auth users. Start with one owner UUID only. |
| `FLYBRAIN_OPS_ALLOWED_ORIGIN` | Exact HTTPS origin of the eventual dashboard, e.g. `https://your-dashboard.example` (origin only; no path or trailing slash). |

Do not use email addresses as allowlist entries. Do not put UUIDs in Git. Do not enable public signup as a shortcut. Obtain the owner UUID from Supabase Dashboard → Authentication → Users, and verify that it is the account intended to administer this project.

The current connector does not expose a safe Edge Function secret-management action. Therefore these two values cannot be set by this repository change; they must be entered in the Supabase Dashboard by an authorized project owner. Do not send the UUID or any secret through chat.

## Deployment sequence (not yet performed)

1. Confirm the owner UUID and the final dashboard HTTPS origin.
2. Set the two Staging secrets above.
3. Apply `supabase/migrations/20261121102000_add_flybrain_ops_summary_rpc.sql` to Staging through the approved migration process.
4. Deploy `supabase/functions/flybrain-ops-summary/index.ts` with `verify_jwt=true`.
5. Run `supabase/tests/flybrain_ops_summary.sql`.
6. Test unauthenticated = 401; authenticated non-allowlisted = 403; allowlisted owner = 200.
7. Verify that the response contains aggregates only and that no sensitive fields or secret material appear in logs or responses.

No step above should be performed against Production.

## Endpoint contract

`GET /functions/v1/flybrain-ops-summary`

- Requires a valid Supabase Auth user JWT.
- Requires the JWT subject/user ID to match the server-side UUID allowlist.
- Accepts browser requests only from the exact configured HTTPS origin.
- Returns `Cache-Control: no-store`.
- Returns aggregate queue, task, latency, lease, event, group-integrity and Cron metrics only.
- Does not return task/group IDs, task payloads, user queries, result data, token hashes, capability tokens, SQL, Cron command text, database credentials, or authorization headers.
- Does not implement retry, cancel, requeue, token rotation, deployment, or any other mutation.

## Verification limits

The SQL was executed in a single `BEGIN … ROLLBACK` test transaction. The returned aggregate structure matched the intended schema against the live Staging data, and the transaction was rolled back. The migration is not applied persistently, the Edge Function is not deployed, and the endpoint is not yet callable.

The owner UUID and dashboard origin are intentionally not guessed. They are the two remaining configuration values before deployment.
