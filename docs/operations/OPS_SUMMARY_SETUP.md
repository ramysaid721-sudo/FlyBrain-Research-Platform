# FlyBrain Operations Dashboard — Staging

**Deployment status:** Edge Function v3 is active in Supabase Staging. The aggregate RPC migration has been applied to Staging. No Production resources were changed.

## Dashboard URL

`https://iudimypauqbkyvjuprgp.supabase.co/functions/v1/flybrain-ops-summary`

The function serves the login page and the protected summary API on the same HTTPS origin. No separate hosting service, Vercel deployment, custom domain, or cross-origin dashboard secret is required.

## Authentication and authorization

- Supabase Auth email/password login.
- No public signup flow is provided by the dashboard.
- The Edge Function checks a valid Auth user JWT and then checks the exact user UUID against `FLYBRAIN_OPS_OWNER_IDS`.
- The owner allowlist secret was entered manually by the project owner in Supabase Dashboard. Its value is never stored in Git or shown in the UI.
- The browser uses only the project's publishable API key. No service-role key or worker token is sent to the browser.
- Access and refresh tokens remain in page memory only; reloading the page requires signing in again.
- The API is same-origin. If `FLYBRAIN_OPS_ALLOWED_ORIGIN` is absent, the function derives the exact HTTPS origin from the project's `SUPABASE_URL`. A configured value, if present, takes precedence and must exactly match.
- Gateway-level JWT verification is disabled because the public login shell must load before sign-in. The protected API route independently validates the Supabase Auth user JWT through `withSupabase({ auth: "user" })`, followed by owner allowlist authorization. Do not remove either check.

## Dashboard scope

Read-only aggregate metrics:
- Queue depth, visible messages, and total message count.
- Task counts by status and retry profile.
- Completed-task latency: average, median, P95, maximum.
- Active and expired leases.
- Worker event counts and event coverage.
- Group integrity and capability-token hash mismatch count.
- Cron schedule and last-24-hour execution reliability.

The response intentionally excludes task/group identifiers, task payloads, user queries, result content, capability tokens and hashes, SQL, Cron command text, credentials, and authorization headers. No task mutation controls are exposed.

## Database RPC

Migration: `supabase/migrations/20261121102000_add_flybrain_ops_summary_rpc.sql`

RPC: `public.flybrain_ops_summary()`

The RPC is SECURITY DEFINER with a fixed `pg_catalog` search path and fully qualified object references. EXECUTE is revoked from PUBLIC, anon, and authenticated; service_role alone can execute it. The Edge Function performs owner authorization before invoking it using its server-side admin client.

## Deployment and verification

- Supabase Staging function: `flybrain-ops-summary`, version 2, ACTIVE.
- `verify_jwt=false` at the gateway only to allow the login page to load. User JWT verification and owner authorization are performed inside the protected API handler.
- Database verification confirmed the RPC exists, anon cannot execute, authenticated cannot execute, and service_role can execute.
- No Production deployment, no GitHub merge, and no change to `main`.
- Runtime browser login and the owner-authorized HTTP 200 response still require an interactive sign-in test by the account owner. Do not claim that the authenticated end-to-end browser test has passed until that test is observed.

## Operational boundaries

This dashboard is read-only. It does not submit, retry, cancel, requeue, or delete tasks; it does not rotate capability tokens, alter cron, change secrets, or deploy services.