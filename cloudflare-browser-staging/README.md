# FlyBrain Browser Worker — Staging

An isolated, authenticated MCP browser service using Cloudflare Browser Run. It is separate from both the existing read-only retrieval bridge and the production Worker.

## Capabilities

- Start guarded remote Chromium sessions with an explicit hostname allowlist.
- Navigate, inspect visible page text, click CSS selectors, enter text, press supported keys, capture screenshots, and close sessions. Click, type, and keypress require the explicit `allowSideEffects: true` argument.
- Reconnect to an existing Browser Run session by session ID on each MCP request.
- Use Cloudflare's Browser binding; no Cloudflare API token is needed at runtime for Browser Run calls. The separate Staging gateway forwards only the explicitly listed browser-session tools.

## Security model

- All MCP requests require `Authorization: Bearer <FLYBRAIN_BROWSER_API_TOKEN>`.
- The token is a Cloudflare Worker secret and must never be committed to Git.
- Each new browser session requires 1–50 explicit hostname patterns. Cloudflare Browser Run guardrails enforce this allowlist for HTTP(S) requests throughout the session.
- The session allowlist cannot be expanded after acquisition. Only HTTPS destinations are accepted.
- Request body is limited to 64 KiB; extracted text and HTML are bounded.
- Browser sessions use a 60-second inactivity keep-alive. Always call `browser_session_close` when finished.
- The endpoint is not public-anonymous. Do not expose the token in URLs, client logs, screenshots, or page content.

## Free-tier budget protection

Cloudflare documents a Workers Free Browser Run allowance of 10 browser minutes per day and up to 3 concurrent browser sessions. This Worker uses short inactivity keep-alive and explicit close operations. Usage is not unlimited; monitor Browser Run usage in the Cloudflare dashboard. No paid upgrade is required by this source code.

## Configure

1. In Cloudflare Workers & Pages, create a new Worker named `flybrain-browser-staging` using the Git repository.
2. Set the Root directory to `cloudflare-browser-staging`.
3. Use `npm run deploy` as the build/deploy command (or use the Git-integrated Workers Builds flow).
4. Ensure the Worker has the Browser Run binding named `BROWSER`. The committed `wrangler.jsonc` declares it.
5. Add a random, high-entropy secret named `FLYBRAIN_BROWSER_API_TOKEN` under Worker Settings → Variables and Secrets. Do not use the Cloudflare API token as this application token.
6. Deploy the staging Worker only. Do not connect this project to the production Worker name.

If using Wrangler manually, set the secret with `npx wrangler secret put FLYBRAIN_BROWSER_API_TOKEN`, then deploy from this directory with `npx wrangler deploy`.

## MCP endpoint

- Health: `GET /health` (does not reveal the secret)
- MCP: `POST /mcp` with JSON-RPC 2.0 and `Authorization: Bearer <FLYBRAIN_BROWSER_API_TOKEN>`

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
```

Local syntax checking does not exercise the remote Browser Run binding. The Staging gateway separately tests bearer-token separation, endpoint validation, and JSON-RPC forwarding. A real deployment smoke test is required to validate account binding and Browser Run quota.

## Explicit non-goals

This Worker does not bypass CAPTCHAs, access controls, or website terms. It does not execute arbitrary shell commands, install packages at runtime, or modify the existing production or read-only staging Worker.
