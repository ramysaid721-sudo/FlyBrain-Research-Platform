# Browser automation layer: Skyvern + Playwright

This directory documents the browser automation layer planned for FlyBrain-NOS / URCAL.

## Architecture

- **Skyvern** is the natural-language browser agent for multi-step website workflows.
- **Playwright** is the deterministic browser automation and regression-test layer.
- The repository's existing `.github/workflows/cloudflare-worker-playwright.yml` installs Chromium and runs the Worker end-to-end suite. Keep it as the low-cost regression path.
- FlyBrain's existing MCP bridge remains the research interface; browser automation is a separate capability and must not weaken its authentication boundary.

## Skyvern: local self-hosted evaluation

The official self-hosted pip path requires Python 3.11–3.14 and installs the local API server:

```bash
python -m pip install --upgrade "skyvern[server]"
skyvern quickstart --install-type server --no-postgres
skyvern run server
```

The local API listens on `http://localhost:8000`. Quickstart configures the LLM provider, browser dependencies, local database, and API credentials. SQLite is suitable for a local evaluation. A vision-capable model is recommended because Skyvern operates from browser screenshots. Model-provider usage may incur charges; do not configure a paid provider without an explicit budget decision.

For the complete web UI and browser runtime, use the official upstream Docker Compose deployment:
https://github.com/Skyvern-AI/skyvern

Official self-hosting guide:
https://github.com/Skyvern-AI/skyvern/blob/main/docs/developers/self-hosted/overview.mdx

## MCP client configuration (local)

After the local server has generated its API key, configure an MCP client to launch Skyvern's MCP adapter:

```json
{
  "mcpServers": {
    "skyvern": {
      "command": "python3",
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

Official MCP guide:
https://github.com/Skyvern-AI/skyvern/blob/main/skyvern/cli/mcp_tools/README.md

## Render workspace inspection (18 November 2026)

The user authorized inspection of Render workspace `Ramy's workspace` (`tea-dbtkammc6qcc73bvo980`).

The live account inspection returned:
- No Render web/background services (including previews).
- No Render Postgres instances.
- No Render Key Value instances.

No resources were created, no deployment was triggered, and no paid plan was selected. A full Skyvern browser stack is not a suitable candidate for a 512 MB free web-service instance: its self-hosted Docker Compose stack includes an API/browser service, PostgreSQL, and UI, and browser workloads are memory-intensive. The official Docker setup guide lists 4 GB+ RAM as a prerequisite:
https://github.com/Skyvern-AI/skyvern/blob/main/docs/developers/self-hosted/docker.mdx

**Deployment gate:** do not create a Render service, database, persistent disk, or paid resource until the user reviews the actual resource plan and explicitly approves any cost. A complete public deployment also requires persistent artifact/session storage, TLS, authentication, and a configured LLM provider.

## Safety and operating policy

1. Start with read-only navigation and extraction against public test pages.
2. Require explicit human approval before submitting forms, sending messages, making purchases, changing account settings, deploying code, or deleting data.
3. Do not store passwords, session cookies, TOTP seeds, or API tokens in prompts, logs, screenshots, test fixtures, or Git.
4. Restrict the self-hosted service behind authentication and TLS before exposing it outside localhost. Enable URL validation when the service can be reached by untrusted users.
5. Keep browser session data and downloads private; they may contain active cookies or access tokens.
6. Record task IDs, target domains, outcomes, and failure reasons without logging secrets.

## Validation checklist

- [ ] Skyvern local API heartbeat responds.
- [ ] Skyvern MCP server starts with the local API key.
- [ ] A read-only browser session opens a public test page and extracts a known title.
- [ ] Playwright CI passes on the repository's supported workflow.
- [ ] No credentials or browser profile data are present in Git history.
- [ ] Mutating actions are gated by explicit approval.
