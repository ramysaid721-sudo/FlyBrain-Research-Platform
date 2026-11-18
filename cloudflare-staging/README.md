# FlyBrain Cloudflare staging bridge

This directory contains a separate staging MCP bridge. It does not replace the production Worker and does not deploy itself.

## Scope
- Exposes one read-only MCP tool: `ask_flybrain`.
- Retrieves source-labelled excerpts from repository README files.
- ChatGPT performs the final synthesis; this Worker does not call a paid language-model provider.
- No write, update, or delete operations are exposed.

## Local checks
After deployment, run:

```bash
bash scripts/smoke-test.sh https://YOUR-STAGING-WORKER.workers.dev
```

## Important
The Worker requires a `FLYBRAIN_PUBLIC_LIMITER` rate-limit binding. Verify that Cloudflare has accepted the staging namespace configuration before deployment.
