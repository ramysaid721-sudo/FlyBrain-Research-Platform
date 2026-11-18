# FlyBrain MCP on Vercel

This deployment replaces the Cloudflare Worker as the MCP gateway. The project uses Vercel Python Functions and the existing authenticated FlyBrain MCP bridge.

## Endpoints

- GET /health — unauthenticated health check
- POST /mcp — Streamable HTTP MCP, protected by FLYBRAIN_CHAT_API_TOKEN

## Deployment

The Vercel project is `flybrain-research-mcp`. Connect this repository to that project or deploy the main branch through the Vercel API. The `api/index.py` entrypoint downloads the pinned v0.14.0 release archive, verifies its Git blob SHA-1, safely extracts it into `/tmp`, then overlays the current `bridge/chat_api.py`, `bridge/mcp_server.py`, and `bridge/browser_use_adapter.py` files from the deployment bundle.

Required Vercel environment variable:
- `FLYBRAIN_CHAT_API_TOKEN` — existing encrypted secret, minimum 32 characters.

Optional:
- `FLYBRAIN_CHAT_LEDGER` — defaults to `/tmp/flybrain-chat.sqlite3`. Vercel function filesystem is ephemeral; this is not durable task history.

## Available MCP tools

- `ask_flybrain`: source-labelled FlyBrain-NOS / URCAL project retrieval.
- `browser_search`: DuckDuckGo HTML search result extraction.
- `browser_fetch`: direct HTTPS HTML/text extraction, without JavaScript execution.
- `browser_research`: search plus multi-source page extraction with exact URLs.
- `browser_use_status`: reports interactive Browser Use readiness separately from HTTP research readiness.
- `browser_run_task`: interactive Browser Use agent; requires a compatible persistent browser host, Chromium and a configured model provider.

## Runtime boundaries

Vercel Python Functions are serverless and do not provide a persistent Chromium host or a local Ollama daemon. The HTTP research tools are therefore independent of Browser Use and use standard-library HTTP/HTML extraction. JavaScript-heavy pages, interactive sessions, durable profiles, background monitoring and long-running parallel browser jobs require a separate browser worker and persistent storage.

No cloud model, hosted browser, database, or paid resource is provisioned by this repository change.
