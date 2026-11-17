# FlyBrain Cloudflare Worker

This directory contains the Cloudflare-native MCP HTTP bridge. It does not run the Python WSGI server or claim to emulate a biological fly brain. It retrieves source-labelled project excerpts from the public repository and returns them to ChatGPT for synthesis.

## Cloudflare Workers Builds settings

- Root directory: `cloudflare-worker`
- Build command: leave blank
- Deploy command: `npx wrangler deploy`
- Preview builds: optional; leave disabled for the first deployment

## Runtime secret

In Worker Settings > Variables and Secrets, add `FLYBRAIN_CHAT_API_TOKEN` as a secret. Use a randomly generated value of at least 32 characters. Never commit the value to Git.

## Endpoints

- `GET /health`
- `POST /mcp` (Bearer authentication; MCP Streamable HTTP)

The free Worker retrieves repository documentation only; no paid model provider is configured. Cloudflare Workers Free limits apply.
