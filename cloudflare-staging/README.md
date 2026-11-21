# FlyBrain Cloudflare Staging Bridge

This is the isolated Staging MCP gateway. It does not replace or modify the Production Worker.

## Existing capability

- `ask_flybrain`: public, read-only, source-labelled retrieval from project documentation.
- ChatGPT performs synthesis; no external model provider is called by this Worker.

## Optional guarded browser capability

The gateway exposes authenticated `browser_session_*` tools only when its private Cloudflare Service binding and client token are configured.

- `FLYBRAIN_BROWSER_ACCESS_TOKEN`: high-entropy client token on the Staging gateway; at least 32 characters.
- `FLYBRAIN_SESSION_SIGNING_KEY`: high-entropy HMAC key on the Browser Worker; at least 32 characters and different from the gateway client token.
- `FLYBRAIN_BROWSER_WORKER`: private Service binding in `wrangler.jsonc` targeting `flybrain-browser-staging`.

No public Browser Worker URL or backend bearer token is required. The Browser Worker has `workers_dev` disabled and is invoked only through the private Service binding. Deploy the Browser Worker before the gateway.

The gateway authenticates external browser-tool requests with the client token. Browser sessions require an explicit hostname allowlist for every new session. Click, type, and keypress operations require `allowSideEffects: true`; without it, they return `approval_required` without touching the browser. Only HTTPS destinations are accepted. Close sessions promptly.

Never put token values in source control or chat. For GitHub Actions deployment, store the two application secrets and the Cloudflare deploy credentials as repository Actions secrets. If using Cloudflare Workers Builds, configure the two application secrets directly in the corresponding Worker settings; Cloudflare manages deployment authorization.

## Free-tier controls

Cloudflare documents 10 browser minutes per day on Workers Free, up to 3 concurrent sessions, and one new session every 20 seconds. The Browser Worker uses a 60-second inactivity timeout; always close sessions when finished. Usage is limited and not guaranteed unlimited.

## Validation

Run the Browser Worker tests and the Staging gateway proxy tests. Perform Wrangler dry-runs for both Workers. After a real Staging deployment, run `scripts/smoke-test.sh` and verify that `/health`, MCP initialization, tool discovery, and a read-only browser snapshot work.

No Production deployment, paid plan, or billing change is authorized by this configuration.

## Staging deployment trigger

The prepared deploy workflow is restricted to this Staging branch. To trigger it from this PR branch without changing the default branch, push a relevant commit whose message explicitly contains `[deploy-staging-only]`. Ordinary commits do not deploy. The workflow also retains a manual `workflow_dispatch` gate for when GitHub exposes it from the default branch.
