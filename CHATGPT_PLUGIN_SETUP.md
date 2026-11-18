# FlyBrain ChatGPT plugin and MCP connection

## MCP tools

The authenticated Streamable HTTP MCP bridge exposes six tools:

- ask_flybrain(question): retrieve source-labelled FlyBrain-NOS and URCAL project evidence.
- browser_use_status(): inspect the optional Browser Use dependency and model configuration.
- browser_run_task(url, goal, max_steps, allow_side_effects): run a bounded browser task against an authorized public HTTPS website.

The browser adapter is local-first: local Chromium plus an OpenAI-compatible local model endpoint (Ollama by default). Search, fetch, and research tools use this same runtime. It is optional and is not activated merely by merging the code. A live run requires the pinned Browser Use dependency, Chromium, and a reachable model endpoint. Account changes, form submissions, purchases, publishing, deletion, uploads, deployments, and similar side effects require explicit approval.

## ChatGPT app route

OpenAI's Plugin Creator workflow is the supported starting point for creating a reusable plugin. Install/connect Plugin Creator, then start a chat with @plugin-creator. Ask it to create a plugin named FlyBrain and expose the six tools listed above through the authenticated MCP endpoint:

https://YOUR-RENDER-SERVICE.onrender.com/mcp

Use Bearer authentication with the generated FLYBRAIN_CHAT_API_TOKEN. Store the token only in the app's designated secret/authentication field, never in instructions, a public document, or repository source.

The plugin should route the exact keyword "ذبابة" or an explicit request to consult FlyBrain to ask_flybrain. For web research, it should inspect browser_use_status first and use browser_search, browser_fetch, or browser_research only when the runtime is ready. For interactive tasks, use browser_run_task. If it is not ready, report that accurately; do not pretend the browser was launched.

Important: direct custom remote MCP server connections are currently limited by ChatGPT plan and app support. Plugin Creator must determine the supported hosting and connection route for this account. Review the generated tool schema and test it before use.

## Browser automation setup

Install the optional dependency from the repository root:

~~~bash
python -m pip install -r requirements-browser-use.txt
uvx browser-use install
~~~

For a local Ollama model, configure the FlyBrain service process with:

~~~bash
BROWSER_USE_PROVIDER=ollama
BROWSER_USE_BASE_URL=http://127.0.0.1:11434/v1
BROWSER_USE_MODEL=qwen2.5:7b
BROWSER_USE_API_KEY=ollama
~~~

Ollama and the selected model must run in the same host/network namespace as the FlyBrain service. A local Ollama endpoint on a phone or laptop is not automatically reachable from Render. Do not expose Ollama publicly.

Optional external model providers:
- OpenAI: BROWSER_USE_PROVIDER=openai and OPENAI_API_KEY.
- Google: BROWSER_USE_PROVIDER=google and GOOGLE_API_KEY.
- Browser Use hosted model/browser: BROWSER_USE_PROVIDER=browser-use-cloud, BROWSER_USE_API_KEY, and BROWSER_USE_ALLOW_CLOUD=true. This may incur charges and is disabled by default.

## Deployment status and limits

The repository contains a Render Blueprint, but the last account inspection found no existing Render services, databases, or Key Value instances. No service has been created or deployed as part of this browser integration. The Render free service has not been proven suitable for hosting a local browser plus model. Do not create any paid resources without explicit approval.

The Cloudflare Worker is a separate lightweight, read-only research endpoint; it cannot run the Python Chromium agent inside the Worker runtime. The Browser Use MCP tools are part of the Python bridge and become reachable only after that bridge is deployed and configured.

## Safety and privacy

- Use only accounts and websites the user is authorized to access.
- Never bypass CAPTCHAs, paywalls, authentication, or access controls.
- Never commit passwords, cookies, TOTP seeds, browser profiles, or API tokens.
- Require explicit user approval before any state-changing action.
- Browser automation tasks may expose page content to the configured model provider. Review the model endpoint and privacy policy before enabling it.
- Without a model provider, Browser Use cannot execute natural-language tasks. The research-only ask_flybrain tool remains independently usable.
