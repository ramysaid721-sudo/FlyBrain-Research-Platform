# FlyBrain Operations Dashboard Deployment

## Current implementation

- Static, read-only dashboard source: `ops-dashboard/index.html`.
- Owner authentication uses Supabase Auth email/password; public signup is not implemented.
- Browser client uses the Staging project's publishable key only. No service-role key, worker token, capability token, or other server secret is included.
- Telemetry is fetched from the owner-protected `flybrain-ops-summary` Edge Function.
- Dashboard displays aggregate queue, task, lease, latency, group-integrity, and Cron metrics only.
- Static deployment branch: `gh-pages`, root `index.html`.
- Source branch: `ops/dashboard-ui-render-20261121`.

## Hosting status

Render static-site creation was attempted in the existing workspace, but Render returned HTTP 402 stating that payment information is required to complete the request. No Render service was created and no card or paid plan was added.

The public GitHub repository supports GitHub Pages at no charge. The `gh-pages` branch has been prepared, but GitHub Pages cannot be enabled by the connected GitHub tool permissions in this workflow. A repository owner must enable it once:

1. Open repository Settings -> Pages.
2. Under Build and deployment, choose Deploy from a branch.
3. Select branch `gh-pages` and folder `/(root)`.
4. Save.

Expected site URL after GitHub confirms the deployment:
`https://ramysaid721-sudo.github.io/FlyBrain-Research-Platform/`

Browser Origin (the value required for the Edge Function CORS allowlist):
`https://ramysaid721-sudo.github.io`

## Remaining Staging activation gates

The UI source is ready, but it is not yet a functioning telemetry dashboard. The following must happen in order:

1. Enable GitHub Pages as described above and verify the published URL.
2. Add the Supabase Edge Function secret `FLYBRAIN_OPS_ALLOWED_ORIGIN` with the exact Origin above (scheme + host only; no path or trailing slash).
3. Confirm `FLYBRAIN_OPS_OWNER_IDS` is set to the intended Auth user's UUID.
4. Obtain explicit confirmation before persistently applying migration `20261121102000_add_flybrain_ops_summary_rpc.sql` and deploying `flybrain-ops-summary` with `verify_jwt=true`.
5. Test unauthenticated (401), authenticated non-owner (403), and allowlisted owner (200), then verify the response contains aggregate metrics only.

No database migration or `flybrain-ops-summary` deployment has been performed. No Production resources were changed.
