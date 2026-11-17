# FlyBrain ChatGPT bridge — validation record

Date: 2026-11-17
Source baseline: v0.14.0 archive plus repository overlay
Runtime: Python 3.13.5

## Implemented
- Authenticated WSGI REST endpoint: GET /health and POST /v1/ask.
- Stateless MCP Streamable HTTP endpoint: POST /mcp; initialize, ping, tools/list, tools/call and notifications.
- MCP exposes one read-only tool, ask_flybrain, protected by the same generated Bearer token.
- No ModelHub provider configured returns source-labelled local research context without an external provider call; ChatGPT can synthesize it.
- Render Blueprint creates a Free Frankfurt web service and generates FLYBRAIN_CHAT_API_TOKEN.
- Overlay installs bridge, MCP server, tests, and corrected runtime version exports into the release archive.

## Fresh local verification on 2026-11-17
- FlyBrain-NOS test suite including REST and MCP bridge tests: 83 passed.
- URCAL test suite: 68 passed.
- Integrated FlyBrain-NOS + URCAL stack runner: 83 passed.
- Distinct suite total: 151 passed (83 + 68); the stack runner independently repeated the 83 FlyBrain tests.
- Python compileall: passed.
- Import smoke test: passed (urcal 0.3.1, flybrain_os 0.13.3).
- Tests were executed against the extracted v0.14.0 archive with the bridge overlay in the local Python 3.13.5 environment.

## Remaining external setup
- Render service has not been created/deployed; its only listed workspace is Ramy's workspace and workspace selection must be confirmed before infrastructure creation.
- ChatGPT Plugin Creator is available but not installed/connected. GitHub and Render connectors are already installed.
- The generated Render token must be added to the plugin's secret authentication setting after deployment.
- The free Render instance sleeps after 15 minutes idle and uses ephemeral local storage. It can operate with the phone off but is not 24/7 always-on.
- No paid ModelHub provider is configured or required for provider-free context retrieval.
- ChatGPT app/plugin selection is not a global keyword interceptor across every ordinary chat.
- No claim is made that the synthetic LIF runtime is a biologically validated Drosophila brain or a natural-language generation system.

## GitHub Actions
GitHub Actions jobs have repeatedly failed before any steps were recorded; no runner logs or definitive root cause were returned. This is separate from the successful local tests above.
