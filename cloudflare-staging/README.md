# FlyBrain Cloudflare staging bridge

This directory contains the isolated staging MCP bridge. It does not replace or modify the production Worker.

## Scope
- Exposes one read-only MCP tool: `ask_flybrain`.
- Retrieves source-labelled excerpts from repository documentation.
- ChatGPT performs the final synthesis; this Worker does not call a paid language-model provider.
- No write, update, or delete operations are exposed.

## Deployment
Deployment is controlled by `.github/workflows/deploy-flybrain-staging.yml`.
- A push to `main` that changes files under `cloudflare-staging/**` triggers the isolated Staging deployment.
- The workflow can also be started manually with GitHub Actions `workflow_dispatch`.
- The workflow uses the GitHub Actions secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`; never put their values in the repository or chat.
- Do not use the old `cloudflare-staging-deployment` branch as a deployment source.

## Smoke test
After a successful Staging deployment, run:

```bash
bash scripts/smoke-test.sh https://YOUR-STAGING-WORKER.workers.dev
```

Verify that `GET /health` reports `rate_limiter_binding: true`, then test MCP initialize, tools/list, and ask_flybrain.

## Safety
The Worker requires the `FLYBRAIN_PUBLIC_LIMITER` rate-limit binding. Keep all changes isolated to Staging; do not deploy or edit the Production Worker.
