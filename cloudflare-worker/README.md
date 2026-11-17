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

The Playwright configuration starts a local Wrangler Worker automatically and injects a disposable test-only bearer token. It does not use or expose the production Cloudflare secret. The current tests cover the browser-visible health endpoint, rejection of unauthenticated MCP requests, and successful MCP initialization. They do not sign in to or change Cloudflare Dashboard settings.
