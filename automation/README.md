# Browser automation layer: Skyvern + Playwright

This directory documents the browser automation layer planned for FlyBrain-NOS / URCAL.

## Architecture

- **Skyvern** is the natural-language browser agent for multi-step website workflows.
- **Playwright** is the deterministic browser automation and regression-test layer.
- The existing `.github/workflows/cloudflare-worker-playwright.yml` already installs Chromium and runs the Worker end-to-end suite. It remains the low-cost, repeatable test path.
- FlyBrain's existing MCP bridge remains the research interface; browser automation is a separate capability and must not weaken its authentication boundary.

## Skyvern: local self-hosted evaluation

Skyvern's official self-hosted quickstart supports a local SQLite setup and a local API server:

```bash
python -m pip install --upgrade "skyvern[server]"
skyvern quickstart --no-postgres
skyvern run server
```

The local API listens on `http://localhost:8000`. Follow the interactive quickstart to configure an LLM provider. A local model can be used where a compatible vision-capable endpoint is available; otherwise the configured provider may incur usage charges.

For the full web UI and browser runtime, use the official upstream Docker Compose deployment:
https://github.com/Skyvern-AI/skyvern

Do not copy secrets into this repository. Store API keys and encryption keys in the deployment platform's secret manager.

## MCP client configuration (local)

After the local server has generated its API key, configure an MCP client to launch Skyvern's MCP adapter:

```json
{
  "mcpServers": {
    "skyvern": {
      "command": "python",
      "args": ["-m", "skyvern", "run", "mcp", "--scope", "operate"],
      "env": {
        "SKYVERN_BASE_URL": "http://localhost:8000",
        "SKYVERN_API_KEY": "REPLACE_WITH_LOCAL_SKYVERN_API_KEY"
      }
    }
  }
}
```

Keep the key in the local client configuration or a secret store; never commit the populated configuration.

## Safety and operating policy

1. Start with read-only navigation and extraction against public test pages.
2. Require explicit human approval before submitting forms, sending messages, making purchases, changing account settings, deploying code, or deleting data.
3. Do not store passwords, session cookies, TOTP seeds, or API tokens in prompts, logs, screenshots, test fixtures, or Git.
4. Restrict the self-hosted service behind authentication and TLS before exposing it outside localhost. Enable URL validation when the service can be reached by untrusted users.
5. Keep browser session data and downloads private; they may contain active cookies or access tokens.
6. Record task IDs, target domains, outcomes, and failure reasons without logging secrets.

## Deployment sizing and cost gate

Do not deploy a public Skyvern instance on a free 512 MB web-service tier. Skyvern's browser workloads are memory-intensive; its current self-hosting guidance recommends at least 4 GB for Docker Compose, and production browser workloads need more headroom. A public deployment also needs persistent storage, a database, TLS, authentication, and a configured LLM provider.

Before creating paid infrastructure, confirm the hosting workspace, available budget, database and persistent-storage plan, and LLM provider. Until then, keep Skyvern local/self-hosted as an evaluation path and use the existing Playwright GitHub Actions workflow for deterministic tests.

## Validation checklist

- [ ] Skyvern local API heartbeat responds.
- [ ] Skyvern MCP server starts with the local API key.
- [ ] A read-only browser session opens a public test page and extracts a known title.
- [ ] Playwright CI passes on the repository's supported workflow.
- [ ] No credentials or browser profile data are present in Git history.
- [ ] Mutating actions are gated by explicit approval.
