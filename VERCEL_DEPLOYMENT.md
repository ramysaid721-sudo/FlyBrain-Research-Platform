# Vercel deployment — FlyBrain MCP

- Project: `flybrain-research-mcp`
- Production URL: https://flybrain-research-mcp.vercel.app
- Runtime: Python 3.13; Frankfurt (`fra1`); Vercel Hobby plan.
- Routes: public `GET /health`; authenticated `POST /mcp`.
- MCP tool: read-only `ask_flybrain(question)`.
- Bearer token: `FLYBRAIN_CHAT_API_TOKEN`, stored as an encrypted Vercel environment variable; never commit its value.

## Evidence corpus

Provider-free mode retrieves source-labelled excerpts from the complete FlyBrain v0.14.0 release documentation tree. On a cold start, the function downloads the pinned public release ZIP from GitHub, verifies its Git blob SHA-1, and extracts it into ephemeral `/tmp` storage. If unavailable, it falls back to repository Markdown. ChatGPT synthesizes the evidence; no paid ModelHub provider is configured.

Run `GET /health?check_corpus=1` to verify the active corpus. The verified production response is `source_corpus: full_release_archive`.

## Operational limits

This is request-driven serverless compute, not an always-running worker. Local `/tmp` storage is ephemeral. Durable ledgers and background work require managed persistent storage and a queue.

The production build completed successfully. `GET /health` returned HTTP 200; `GET /mcp` returned HTTP 405 with `Allow: POST`, as required by MCP. An authenticated MCP POST/client test remains necessary before connecting a ChatGPT app.

The initial deployment was uploaded through the Vercel API because the Vercel account did not yet have a GitHub Login Connection. Connect GitHub in Vercel to enable automatic repository deployments. Never commit the bearer token.
