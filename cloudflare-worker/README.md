# FlyBrain Cloudflare Worker

This directory contains the Cloudflare-native MCP HTTP bridge. It does not run the Python WSGI server or claim to emulate a biological fly brain. It retrieves source-labelled project excerpts from the public repository and returns them to ChatGPT for synthesis.

## Cloudflare Workers Builds settings

- Root directory: `cloudflare-worker`
- Build command: leave blank
- Deploy command: `npx wrangler deploy`
- Preview builds: optional; leave disabled for the first deployment

## Endpoints and access model

- `GET /health`
- `POST /mcp` (public, read-only MCP Streamable HTTP)

The only exposed tool is `ask_flybrain(question)`. It retrieves excerpts from the three public project README files. It cannot write, edit, delete, access private repositories, or access Cloudflare account settings. No production API token or paid model provider is required.

The MCP endpoint applies a Cloudflare rate-limit binding configured for approximately 30 requests per minute per client IP and rejects declared request bodies larger than 64 KiB. Cloudflare documents that this rate limiter is approximate and is enforced separately in each Cloudflare location; it is a protective throttle, not a strict global quota. Public access means anyone who discovers the endpoint can call this read-only tool.

Cloudflare Workers Free currently documents a limit of 100,000 requests per day. Monitor usage in the Cloudflare dashboard; do not upgrade to a paid plan for this project without a separate explicit decision.

## Playwright browser automation and tests

Playwright is configured in this directory to automate Chromium and verify the local Worker before deployment.

```bash
npm install
npx playwright install chromium
npm run typecheck
npm run test:e2e
```

Useful interactive modes:

```bash
npm run test:e2e:headed
npm run test:e2e:ui
```

The Playwright configuration starts a local Wrangler Worker automatically. Tests cover the browser-visible health endpoint, unauthenticated MCP initialization, the read-only tool list, and retrieval from the public repository. They do not sign in to or change Cloudflare Dashboard settings.