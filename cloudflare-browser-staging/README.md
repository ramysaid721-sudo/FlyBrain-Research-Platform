# FlyBrain Browser Worker — Staging

An isolated, authenticated MCP browser service using Cloudflare Browser Run and the Cloudflare-compatible Playwright runtime. It is separate from the existing retrieval bridge and production Worker.

## Capabilities

- Render public HTTPS pages with Playwright on Cloudflare Browser Run.
- Restrict every page request, including redirects and subresources, to the exact target hostname.
- Start guarded remote Chromium sessions with explicit hostname allowlists.
- Navigate, inspect visible page text, click CSS selectors, enter text, press supported keys, capture screenshots, and close sessions.
- Keep browser sessions short and close them after use.

## Provider routing in FlyBrain

The Python adapter uses a zero-cost-first policy:

1. Plain HTTPS extraction is attempted first.
2. If the page appears to require JavaScript or HTTP extraction fails, FlyBrain tries the configured Cloudflare Browser Run + Playwright endpoint.
3. If Cloudflare is unavailable or fails, FlyBrain tries Browserless only when its token and explicit usage flag are configured.
4. If rendered providers are unavailable, the original HTTP result is returned with a warning that JavaScript content may be incomplete.

Playwright is an automation engine, not a hosted browser provider. In this setup it runs on Cloudflare Browser Run. Browserless is a separate hosted fallback.

## Security model

- All MCP requests require `Authorization: Bearer <FLYBRAIN_BROWSER_API_TOKEN>`.
- The token is a Cloudflare Worker secret and must never be committed to Git.
- The Playwright fetch tool accepts only public HTTPS targets and intercepts browser requests, allowing only the exact target hostname.
- Interactive sessions require 1–50 explicit hostname patterns enforced by Browser Run guardrails.
- Request body and extracted content are bounded.
- No credentials are sent to target pages. The system does not bypass CAPTCHAs, logins, paywalls, access controls, or website security.

## Cost controls

- Cloudflare documents 10 browser minutes/day and up to 3 concurrent Browser Run sessions on Workers Free. Usage is finite; verify the account plan before enabling the adapter.
- Browserless Free currently lists 1,000 units/month, 2 concurrent browsers, and 2-minute sessions; the free allowance rejects new requests after it is exhausted.
- Both remote providers remain disabled unless their credentials and explicit usage flags are configured.
- FlyBrain defaults to the HTTP path and does not automatically enable paid plans or billing.

## Configure staging only

Cloudflare Worker:
1. Set the Worker name to `flybrain-browser-staging`.
2. Set the root directory to `cloudflare-browser-staging`.
3. Ensure the Browser binding is named `BROWSER`.
4. Add `FLYBRAIN_BROWSER_API_TOKEN` as a Worker secret.
5. Deploy this staging Worker only and verify `/health`.

FlyBrain Vercel Preview environment (branch `flybrain-browser-worker-staging`):
- `FLYBRAIN_BROWSER_WORKER_URL`: the full HTTPS Worker MCP URL ending in `/mcp`.
- `FLYBRAIN_BROWSER_API_TOKEN`: the same application secret configured on the Worker.
- `FLYBRAIN_BROWSER_RUN_ALLOW_USAGE`: set to `true` only after verifying the account is on a no-charge plan and the free quota is acceptable.
- `BROWSERLESS_TOKEN`: optional Browserless free-plan token.
- `BROWSERLESS_ALLOW_USAGE`: set to `true` only if the Browserless free plan is selected and overage is disabled/rejected by the provider.
- `FLYBRAIN_WEB_FETCH_PROVIDER`: leave unset or set to `auto` for automatic failover.

Do not place these values in GitHub files, commit messages, logs, or issue comments. Use Vercel Preview variables scoped to the staging branch, never Production.

## MCP endpoint

- Health: `GET /health`
- MCP: `POST /mcp`
- Playwright rendering tool: `browser_playwright_fetch(url)`
- Session tools: `browser_session_open`, `browser_session_navigate`, `browser_session_snapshot`, `browser_session_click`, `browser_session_type`, `browser_session_press`, `browser_session_screenshot`, `browser_session_close`

## Local checks

```sh
npm install --no-audit --no-fund
npm run check
npm test
npx wrangler deploy --dry-run
```

A dry run does not prove that the live Browser Run binding or authentication secret is configured. A live smoke test is required after staging deployment.
