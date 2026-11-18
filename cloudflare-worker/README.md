# FlyBrain Cloudflare Worker

This directory contains the Cloudflare-native MCP HTTP gateway. It retrieves source-labelled project excerpts and can securely proxy browser automation requests to the authenticated Python FlyBrain MCP bridge. It does not run Chromium or a Python model inside the Worker runtime.

## Cloudflare Workers Builds settings

- Root directory: cloudflare-worker
- Build command: leave blank
- Deploy command: npx wrangler deploy
- Preview builds: optional; leave disabled for the first deployment

## Endpoints and access model

- GET /health
- POST /mcp

The MCP catalog exposes six tools:
- ask_flybrain(question): public read-only project retrieval.
- browser_use_status(): checks the Browser Use service through the authenticated backend.
- browser_search(query, max_results): public web search through the rendered browser agent.
- browser_fetch(url, output_format, include_links): rendered page extraction.
- browser_research(question, max_sources): multi-source research with source URLs.
- browser_run_task(url, goal, max_steps, allow_side_effects): bounded interactive browser workflow.

The research tool remains public and read-only. All browser_* calls require a separate Bearer token and are forwarded to the authenticated Python MCP backend. This prevents anonymous visitors from using browser resources or the configured model.

## Browser proxy configuration

The Worker must have these three environment values/secrets before browser tools can run:

- FLYBRAIN_BROWSER_ACCESS_TOKEN: separate secret used by the ChatGPT plugin to authorize browser_* calls to this Worker.
- BROWSER_AUTOMATION_MCP_URL: HTTPS URL of the Python MCP backend, ending in /mcp.
- BROWSER_AUTOMATION_TOKEN: Bearer token accepted by the Python backend (the backend's FLYBRAIN_CHAT_API_TOKEN).

Keep all tokens in Cloudflare Worker secrets, not in wrangler.jsonc or Git. The ChatGPT plugin must send FLYBRAIN_BROWSER_ACCESS_TOKEN as its Bearer credential. The Worker then uses BROWSER_AUTOMATION_TOKEN for the backend hop. Do not reuse the public research endpoint as the private browser backend.

Until the Python backend is deployed and all three values are configured, browser tools return a clear not-configured/unauthorized response. The current repository does not contain a deployed Browser Use backend; no Render service or paid resource is created by this change.

## Backend requirements

The Python backend must use the FlyBrain bridge from the repository root and install the optional dependency:

~~~bash
python -m pip install -r requirements-browser-use.txt
uvx browser-use install
~~~

Local-first model settings use an Ollama-compatible endpoint reachable from the same host/network namespace as the Python service. A Render service cannot reach Ollama running on a phone or laptop at 127.0.0.1. Do not expose a local model endpoint to the public internet. Cloud model/browser providers are opt-in and may incur charges.

See automation/README.md and CHATGPT_PLUGIN_SETUP.md for provider setup and the remaining capability roadmap.

## Rate limits and tests

The MCP endpoint applies a Cloudflare rate-limit binding configured for approximately 30 requests per minute per client IP. The Worker rejects declared request bodies larger than 64 KiB. Public access means anyone who discovers the endpoint can call the read-only research tool; browser tools additionally require the dedicated Bearer token.

Cloudflare Workers Free currently documents a limit of 100,000 requests per day. Monitor usage in the dashboard; do not upgrade to a paid plan for this project without a separate explicit decision.

Playwright checks:

~~~bash
npm install
npx playwright install chromium
npm run typecheck
npm run test:e2e
~~~

The tests cover the health endpoint, unauthenticated MCP initialization, the six-tool catalog, public read-only research retrieval, and rejection of unauthenticated browser-tool calls.
