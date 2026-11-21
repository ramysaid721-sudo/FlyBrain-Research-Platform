# FlyBrain Cloudflare Staging Bridge

This is the isolated Staging MCP gateway. It does not replace or modify the Production Worker.

## Existing capability
- `ask_flybrain`: public, read-only, source-labelled retrieval from project documentation.
- ChatGPT performs synthesis; no external model provider is called by this Worker.

## Optional guarded browser capability
The gateway exposes authenticated `browser_session_*` tools only when a separate Cloudflare Browser Run Worker is configured.

Deploy `cloudflare-browser-staging` as a distinct Worker first, then configure these variables/secrets on this Staging gateway. The manual GitHub Actions deployment workflow now discovers the Browser Worker's `workers.dev` URL from Wrangler's deploy output and sets `BROWSER_AUTOMATION_MCP_URL` on the Staging gateway automatically; do not create a GitHub secret for that URL when using the workflow:

- `FLYBRAIN_BROWSER_ACCESS_TOKEN`: high-entropy client token used by the MCP caller; at least 32 characters.
- `BROWSER_AUTOMATION_MCP_URL`: exact HTTPS `workers.dev` MCP endpoint ending in `/mcp`.
- `BROWSER_AUTOMATION_TOKEN`: backend token; must match the Browser Worker's `FLYBRAIN_BROWSER_API_TOKEN` and must be different from the client token.

Never put token values in source control or chat. The gateway does not list browser tools until all three settings are valid. Browser calls require the client bearer token and are forwarded to the dedicated Browser Worker using the separate backend token.

The Browser Worker requires an explicit hostname allowlist for every new session. Click, type, and keypress operations require `allowSideEffects: true`; without it, they return `approval_required` without touching the browser. Only HTTPS destinations are accepted. Close sessions promptly.

## Free-tier controls
Cloudflare currently documents 10 browser minutes per day on Workers Free, up to 3 concurrent sessions, and one new session every 20 seconds. The browser Worker uses a 60-second inactivity timeout; always close sessions when finished. Usage is limited and not guaranteed unlimited.

## Validation
Run the Browser Worker tests and the Staging gateway proxy tests. Perform Wrangler dry-runs for both Workers. After a real Staging deployment, run `scripts/smoke-test.sh` and verify that `/health`, MCP initialization, tool discovery, and a read-only browser snapshot work.

No Production deployment, paid plan, or billing change is authorized by this configuration.
