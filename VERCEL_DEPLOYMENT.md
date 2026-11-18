# FlyBrain MCP on Vercel

The production MCP gateway has been migrated from Cloudflare Worker to the existing Vercel project `flybrain-research-mcp`.

## Production endpoints

- GET / — public service and capability health response.
- GET /health — same public health response.
- POST /mcp — stateless Streamable HTTP MCP endpoint.
- Plugin connection: https://flybrain-research-mcp.vercel.app/mcp

Production deployment is currently aliased to `flybrain-research-mcp.vercel.app` and runs in region `fra1`. The latest confirmed production deployment is `dpl_GYi144aUQq74qutC8B12bgSeN7R9`, state `READY`, version `0.16.0`.

## Authentication and public access

The ChatGPT plugin uses unauthenticated, read-only access to:
- MCP `initialize`, `ping`, and `tools/list`.
- `ask_flybrain`, `browser_search`, `browser_fetch`, `browser_research`, and `browser_use_status`.

These public calls have a per-instance limit of 60 requests per minute. This is a best-effort per-instance guard, not a distributed rate-limit service.

`browser_run_task` and the internal `/v1/ask` REST endpoint remain protected by the encrypted Vercel environment variable `FLYBRAIN_CHAT_API_TOKEN`. Never place that token in the plugin package, documentation intended for public distribution, or repository source.

## Runtime

The Vercel Python Function:
1. Downloads the pinned v0.14.0 release archive from the repository.
2. Verifies the archive's Git blob SHA-1 before extraction.
3. Rejects unsafe archive paths.
4. Extracts the release into `/tmp`.
5. Overlays the current `bridge/chat_api.py`, `bridge/mcp_server.py`, and `bridge/browser_use_adapter.py` files.

The only required production environment variable is `FLYBRAIN_CHAT_API_TOKEN`. It exists in encrypted form and applies to production and preview. The optional `FLYBRAIN_CHAT_LEDGER` path defaults to `/tmp/flybrain-chat.sqlite3`; Vercel filesystem storage is ephemeral and must not be treated as durable task history.

## Available MCP tools

- `ask_flybrain`: source-labelled FlyBrain-NOS and URCAL project retrieval.
- `browser_search`: public DuckDuckGo HTML search.
- `browser_fetch`: public HTTPS HTML/text extraction. No JavaScript execution.
- `browser_research`: search plus extraction of up to six public source pages; ChatGPT performs the synthesis.
- `browser_use_status`: separate status for HTTP research and interactive Browser Use.
- `browser_run_task`: protected interactive browser tool; unavailable until a separate browser host, Chromium, Browser Use, and model endpoint are configured.

## Known runtime boundaries

The production health endpoint was fetched successfully and returned HTTP research readiness as true, with interactive browser readiness false. The current deployment does not provide:
- JavaScript-rendered browser sessions.
- Persistent browser profiles or authenticated sessions.
- Durable task queues or background workers.
- Scheduled webpage monitors.
- Fully autonomous multi-step website interactions.

Those capabilities require a separately deployed browser worker and durable state/queue layer. No paid cloud browser, hosted model, database, or persistent storage was provisioned.

## Deployment and validation

The production build completed successfully using Python 3.13. The public root and `/health` endpoints were fetched and returned the expected service status and capability list. Runtime logs show successful HTTP 200 responses.

GitHub Actions currently fails before any job steps are created (runner ID/name and step list are empty). This is an infrastructure/runner-stage failure, not evidence that the Python test suite passed or failed. The test suite remains unverified in GitHub Actions. Do not claim test success until a job actually executes its steps.

No paid resources or new storage services are provisioned by this deployment.
