# FlyBrain – ذبابة: ChatGPT connection and runtime status

## Live MCP gateway

The production MCP endpoint is hosted on Vercel, not Cloudflare:

- Health: https://flybrain-research-mcp.vercel.app/
- Health details: https://flybrain-research-mcp.vercel.app/health
- Streamable HTTP MCP: https://flybrain-research-mcp.vercel.app/mcp

The ChatGPT plugin package `flybrain-zubaba` version `0.2.0` points to this endpoint using unauthenticated read-only MCP access. Do not add a bearer token to the plugin manifest or skill files.

## Available read-only tools

- `ask_flybrain(question)`: retrieve source-labelled FlyBrain-NOS and URCAL project evidence.
- `browser_search(query, max_results)`: search public web results through DuckDuckGo HTML.
- `browser_fetch(url, output_format, include_links)`: extract readable text, page title, description, and links from a public HTTPS page.
- `browser_research(question, max_sources)`: search and fetch up to six public sources; returns source excerpts and exact URLs for ChatGPT to synthesize.
- `browser_use_status()`: report HTTP research readiness and interactive browser readiness separately.

The public MCP surface includes `initialize`, `ping`, and `tools/list`. Public calls are guarded by a per-instance rate limit of 60 requests per minute. The rate limiter is not a distributed quota system and may reset when a serverless instance restarts.

## Protected interactive automation

- `browser_run_task(url, goal, max_steps, allow_side_effects)` is present in the server tool catalogue but is not exposed through the public plugin connection.
- It requires the server-held `FLYBRAIN_CHAT_API_TOKEN`, Browser Use, Chromium, and a reachable configured model on a compatible browser host.
- The current Vercel deployment reports `interactive_browser_ready=false`; Browser Use is not installed in that serverless runtime.
- No persistent browser profiles, authenticated sessions, durable background jobs, scheduled monitors, or interactive JavaScript browser automation are currently active.

Do not claim that the service has TinyFish-equivalent browser automation until a separate browser worker has been deployed and tested.

## Runtime architecture

```text
ChatGPT plugin: FlyBrain – ذبابة
           |
           | public, read-only MCP over HTTPS
           v
Vercel Python Function
           |
           +--> FlyBrain-NOS / URCAL project retrieval
           +--> Public web search (DuckDuckGo HTML)
           +--> Safe HTTPS page extraction
           +--> Multi-source evidence collection
           |
           +--> Protected browser_run_task (not active)
                Requires separate browser host + model
```

The Vercel function downloads the pinned FlyBrain v0.14.0 release archive, verifies its Git blob SHA-1, safely extracts it into temporary storage, and overlays the current bridge files from the deployment bundle. The `FLYBRAIN_CHAT_API_TOKEN` environment variable is encrypted in Vercel and is never included in the public plugin package.

## Browser worker options

The repository includes the optional Browser Use adapter and a pinned dependency file. A separate worker needs:
- Browser Use and Chromium installed.
- A reachable model endpoint (local Ollama or a separately authorized external provider).
- An HTTPS MCP backend URL and a server-side bearer token.
- A compatible host with enough memory and stable process lifetime for browser sessions.

Render was inspected previously and had no services, databases, or Key Value stores. No Render service, database, hosted model, or paid browser was created. Do not provision paid resources without separate approval. Vercel serverless functions are not a persistent Chromium/Ollama host.

## Safety

- Public plugin tools are read-only. They must not submit forms, change accounts, publish, delete, purchase, deploy, or retrieve secrets.
- Interactive browser actions require separate bearer authentication and explicit approval for state-changing goals.
- Only use sites and accounts the user is authorized to access.
- Never bypass CAPTCHAs, paywalls, authentication, or access controls.
- Do not expose passwords, cookies, API keys, browser profiles, or private account data to page content or model providers.
- HTTP extraction does not execute JavaScript and may not capture content loaded dynamically by a website.
- ChatGPT synthesizes the retrieved evidence; the MCP server is a retrieval and automation interface, not a standalone language model.
- Do not describe the synthetic LIF runtime as a biologically validated complete Drosophila brain or a standalone language model.

## Plugin behavior

When the user says `ذبابة` in a FlyBrain/URCAL context:
1. Call `ask_flybrain` with the actual question.
2. For current public-web information, call `browser_search`; for a known URL, call `browser_fetch`.
3. For multi-source research, call `browser_research` and synthesize its returned excerpts in ChatGPT.
4. Preserve exact source paths and URLs. Distinguish documented project facts, externally retrieved evidence, interpretation, hypotheses, and recommendations.
5. If a tool returns no evidence or a fetch fails, report that accurately rather than inventing results.
