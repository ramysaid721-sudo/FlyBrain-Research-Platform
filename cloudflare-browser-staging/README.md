# FlyBrain Browser Worker — Staging

An isolated internal MCP browser service using Cloudflare Browser Run. It is separate from both the existing read-only retrieval bridge and the production Worker.

## Capabilities

- Start guarded remote Chromium sessions with an explicit hostname allowlist.
- Navigate, inspect visible page text, click CSS selectors, enter text, press supported keys, capture screenshots, and close sessions. Click, type, and keypress require the explicit `allowSideEffects: true` argument.
- Reconnect to an existing Browser Run session by signed session ID on each MCP request.
- Use Cloudflare's Browser binding. The Browser Worker is reached through a private Cloudflare Service binding from the Staging MCP gateway; it has no public `workers.dev` endpoint.

## Security model

- `workers_dev` is disabled. Do not add a public route to this Worker.
- The gateway authenticates the external caller with `FLYBRAIN_BROWSER_ACCESS_TOKEN` before invoking this Worker through the `FLYBRAIN_BROWSER_WORKER` Service binding.
- Cloudflare Service bindings restrict invocation to Workers that explicitly declare the binding in the same Cloudflare account. The Browser Worker does not need a second bearer token or a public URL.
- Set a high-entropy secret named `FLYBRAIN_SESSION_SIGNING_KEY` on this Worker (at least 32 characters). It is used only to sign and verify browser session handles. Never commit it or reuse the gateway client token.
- Each new browser session requires 1–50 explicit hostname patterns. Cloudflare Browser Run guardrails enforce this allowlist for HTTP(S) requests throughout the session.
- The session allowlist cannot be expanded after acquisition. Only HTTPS destinations are accepted.
- Request body is limited to 64 KiB; extracted text and HTML are bounded.
- Browser sessions use a 60-second inactivity keep-alive. Always call `browser_session_close` when finished.

## Free-tier budget protection

Cloudflare documents a Workers Free Browser Run allowance of 10 browser minutes per day and up to 3 concurrent browser sessions. This Worker uses short inactivity keep-alive and explicit close operations. Usage is not unlimited; monitor Browser Run usage in the Cloudflare dashboard. No paid upgrade is required by this source code.

## Configure

1. Create a distinct Worker named `flybrain-browser-staging` from this repository, with root directory `cloudflare-browser-staging`.
2. Ensure the Worker has the Browser Run binding named `BROWSER`; the committed `wrangler.jsonc` declares it.
3. Add the `FLYBRAIN_SESSION_SIGNING_KEY` secret in Worker Settings → Variables and Secrets.
4. Keep `workers_dev` disabled and deploy this Worker before the Staging gateway. The gateway's Wrangler config declares the private service binding to this exact Worker name.

For GitHub Actions deployment, store `FLYBRAIN_SESSION_SIGNING_KEY` as a GitHub Actions secret. For Cloudflare Workers Builds, configure it directly as a Worker secret instead.

## Internal MCP interface

The Browser Worker handles `POST /mcp` and `GET /health`, but these routes are intentionally not exposed on the public Internet. The Staging gateway invokes them through its `FLYBRAIN_BROWSER_WORKER` Service binding.

## Tools

- `browser_session_open(url, allowedDomains)`
- `browser_session_navigate(sessionId, url)`
- `browser_session_snapshot(sessionId, includeHtml?)`
- `browser_session_click(sessionId, selector)`
- `browser_session_type(sessionId, selector, text)`
- `browser_session_press(sessionId, key)`
- `browser_session_screenshot(sessionId)`
- `browser_session_close(sessionId)`

## Local checks

```sh
npm install
npm run check
npm test
```

Local syntax checking does not exercise the remote Browser Run binding. A real Staging deployment smoke test is required to validate account binding and Browser Run quota.

## Explicit non-goals

This Worker does not bypass CAPTCHAs, access controls, or website terms. It does not execute arbitrary shell commands, install packages at runtime, or modify the existing production or read-only staging Worker.
