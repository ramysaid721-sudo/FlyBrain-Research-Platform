# FlyBrain web research and browser automation

This layer is designed to replace the capabilities needed from TinyFish with an open-source, provider-neutral stack. It does not copy TinyFish source code or claim feature parity before each capability has been implemented and tested.

## Capability map

| Capability | FlyBrain implementation | State |
|---|---|---|
| Goal-driven browser navigation | Browser Use Python agent | Adapter added; runtime not yet activated |
| Click, type, scroll, pagination, dynamic pages | Browser Use + Chromium | Requires configured model and browser runtime |
| Deterministic browser scripts and regression tests | Playwright | Existing workflow; its CI run still needs diagnosis |
| Browser screenshots and step traces | Browser Use history + Playwright artifacts | Not yet exposed as MCP outputs |
| Structured extraction | Browser Use task result | Initial text-result adapter |
| Search and multi-page research | Search provider + fetch/extract pipeline | Planned; Browser Use alone does not provide a full search index |
| Rendered page fetch (Markdown/HTML/JSON) | Browser rendering + extraction | Planned dedicated MCP tools |
| Authenticated sessions and reusable profiles | Isolated browser profile store | Not implemented; no credentials are stored by this adapter |
| Run status, history, cancellation and retries | Persistent task registry | Planned |
| Parallel multi-site workflows | Bounded worker pool | Planned |
| Monitoring and change alerts | Scheduler + snapshots + diff engine | Planned |
| Enrichment and dataset exports | Research pipeline + CSV/JSON export | Planned |
| MCP access | FlyBrain MCP tools | Initial browser_run_task and browser_use_status tools added |

## Browser Use adapter

The repository uses Browser Use 1.0.0 with an exact version pin. The local-first default is:

- Browser: local Chromium (Browser("chromium")).
- Model: an OpenAI-compatible local endpoint, defaulting to Ollama at http://127.0.0.1:11434/v1.
- Model name: qwen2.5:7b by default; configure a model already available on the local Ollama host.
- Cloud browser/model providers are opt-in and must not be enabled without reviewing possible usage charges.

Install the optional dependency:

~~~bash
python -m pip install -r requirements-browser-use.txt
uvx browser-use install
~~~

Environment configuration for a local Ollama model:

~~~bash
BROWSER_USE_PROVIDER=ollama
BROWSER_USE_BASE_URL=http://127.0.0.1:11434/v1
BROWSER_USE_MODEL=qwen2.5:7b
BROWSER_USE_API_KEY=ollama
~~~

The local model and Ollama service must be available on the same machine/network namespace as FlyBrain. A local endpoint on a developer laptop is not reachable from a remote Render service unless a secure private network is deliberately configured.

Other supported providers:
- BROWSER_USE_PROVIDER=openai with OPENAI_API_KEY.
- BROWSER_USE_PROVIDER=google with GOOGLE_API_KEY.
- BROWSER_USE_PROVIDER=browser-use-cloud with BROWSER_USE_API_KEY and explicit BROWSER_USE_ALLOW_CLOUD=true. This mode may incur charges and is disabled by default.

## MCP tools

- browser_use_status(): reports whether the optional dependency and selected model configuration are present. It does not claim the browser is live until a task succeeds.
- browser_run_task(url, goal, max_steps=12, allow_side_effects=false): bounded goal-driven browser run. HTTPS targets only; local/private IP and internal hostnames are rejected. Potentially mutating goals are blocked unless the caller explicitly approves them.

The adapter does not bypass CAPTCHAs, paywalls, authentication, or access controls. It must not be used to access sites or accounts without authorization.

## Safety and deployment

1. Keep browser automation behind authentication; do not expose an unauthenticated browser-control endpoint.
2. Start with public, read-only pages and short step limits.
3. Require explicit approval before form submission, sending messages, purchases, bookings, uploads, publishing, deployments, deletion, or account/security changes.
4. Do not put passwords, cookies, TOTP seeds, API tokens, or personal browser profiles in prompts, logs, screenshots, fixtures, or Git.
5. Do not expose a local Ollama endpoint to the public internet.
6. The Browser Use Python library is MIT-licensed; model inference and hosted browser services may have separate pricing and terms.
7. Do not create a paid cloud browser, model, Render service, database, or persistent disk without explicit user approval.

## Remaining work before claiming TinyFish replacement

- Add a persistent task store with task IDs, status, retries, cancellation, screenshots, and audit events.
- Add dedicated search, rendered fetch, multi-source research, structured extraction, and source citation tools.
- Add isolated authenticated browser profiles with a credential vault and explicit access controls.
- Add parallel execution with concurrency and domain rate limits.
- Add monitoring schedules, page snapshots, diffs, and alert delivery.
- Add JSON/CSV dataset exports and enrichment workflows.
- Run integration tests on a real configured browser/model pair and validate the deployed MCP endpoint.

The full TinyFish-equivalent capability set is a staged implementation, not a claim that this initial adapter already provides every hosted TinyFish feature.
