# Vercel deployment — FlyBrain MCP

This deployment is a serverless alternative to the Render Blueprint. It reuses the repository's existing read-only MCP transport and exposes:

- `GET /health` — public health check.
- `POST /mcp` — Streamable HTTP MCP endpoint, protected by Bearer authentication.
- `ask_flybrain(question)` — the sole read-only MCP tool.

## Hosting

- Vercel project: `flybrain-research-mcp`
- Production URL: https://flybrain-research-mcp.vercel.app
- Runtime: Python 3.13
- Region: Frankfurt (`fra1`)
- Plan: Hobby
- Authentication secret: `FLYBRAIN_CHAT_API_TOKEN` (stored as an encrypted Vercel environment variable; never commit its value).

## Operating mode and scope

This deployment intentionally uses provider-free mode. It returns relevant source-labelled excerpts from the repository's Markdown documentation; ChatGPT synthesizes the answer. It does not call paid ModelHub providers.

The deployment bundle includes the project README and ChatGPT integration documentation. It does not yet bundle the full release ZIP's internal FlyBrain-NOS and URCAL documentation tree, so the evidence corpus is narrower than the full Render release build.

The serverless function is request-driven, not an always-running process. Its local `/tmp` storage is ephemeral. Do not use it for durable ledgers or background workers without adding managed persistent storage and a queue.

## Verification

The production deployment was built successfully and `GET /health` returned HTTP 200 with service status `ok`. A GET to `/mcp` correctly returns HTTP 405 because MCP requests must use POST. Complete authenticated MCP client testing is still required before treating the endpoint as fully integrated with a ChatGPT app.

## Redeployment

The initial Vercel deployment was uploaded through the Vercel deployment API because the account did not yet have a GitHub Login Connection for Vercel. To enable automatic deployments from GitHub, connect the GitHub account in Vercel and link this repository to the project. Keep the bearer token in Vercel environment variables only.
