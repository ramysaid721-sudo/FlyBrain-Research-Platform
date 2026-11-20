# FlyBrain Read-Only Control Plane — Architecture and Safety Plan

**Status:** design only; no endpoint, schema, policy, or deployment changed.
**Scope:** Supabase Staging operations and the separate Vercel production MCP service.
**Cost policy:** free-tier compatible; no paid services or provider usage.
**Data policy:** operational aggregates only. Never expose task payloads, query text, results, capability-token hashes, capability tokens, worker credentials, authorization headers, or Cron command text.

## 1. Verified system boundaries

FlyBrain currently has two distinct operational planes. They must not be presented as one deployment:

| Plane | Verified role | Current state |
|---|---|---|
| Vercel `flybrain-research-mcp` | Production ChatGPT MCP gateway for source-labelled project retrieval and public HTTP research tools | Project exists; latest listed production deployment is READY and was built from `main` commit `7880b77a195ced5a43dad75f4859e735a2b40edf`. |
| Supabase Staging `iudimypauqbkyvjuprgp` | Staging MCP, Crossref research task queue, protected worker, Cron and operational ledger | Project ACTIVE_HEALTHY; MCP v28 and Worker v8 ACTIVE; OpenRouter proxy v12 ACTIVE but inference remains disabled. |
| Cloudflare staging branch | Independent read-only MCP prototype | Source and dry-run exist; this is not the active Supabase queue/worker path and is not a deployed replacement. |

The Vercel production gateway is not the Supabase Staging worker. The Vercel MCP runtime and the Supabase task queue have different tools, state, credentials, and operational boundaries.

## 2. Existing owner-facing operations interface

The safest working operations surface is the Supabase SQL Notebook, because access is mediated by Supabase project membership rather than a newly exposed public endpoint:

- [FlyBrain Staging Operations v2](https://supabase.com/dashboard/project/iudimypauqbkyvjuprgp/explorer/notebook/0375b305-88ac-49b9-b29c-f93c7a8cb45f)
- 10 read-only SQL cells covering queue depth, task-state/retry aggregates, end-to-end latency, lease health, event telemetry and coverage, group integrity/token-hash alignment, Cron schedule and Cron run reliability.
- The notebook queries deliberately omit sensitive payload fields and Cron command text.

The notebook is an operational dashboard for a project member, not a public user-facing web application. It does not provide task mutation controls.

## 3. Why a new public dashboard API is not safe yet

The current Staging RPCs that read operational/private tables are restricted to `service_role`. The public MCP endpoint is intentionally exposed for a limited tool surface. A browser page must never receive the Supabase `service_role` key, worker capability secret, or a reusable task capability token.

A public unauthenticated summary endpoint would expose internal operational metadata. A client-side secret embedded in JavaScript would not be a secret. Therefore, do not add a dashboard route to the public MCP gateway or query Supabase directly from browser code.

Before a separate dashboard API can be implemented, one of these server-enforced identity models must be selected and verified:

1. **Supabase Auth allowlist:** verify a signed Supabase user JWT at the Edge Function, then authorize only an explicit owner UUID allowlist held server-side. The browser receives only the user's own session token; service-role access remains server-side.
2. **Hosting access control:** protect the dashboard and its API with a verified Vercel access-control mechanism (for example, SSO/password protection) before serving any operational data.

Do not assume that merely enabling `verify_jwt` authorizes only the project owner: it validates a project JWT, not an owner allowlist. Do not enable broad signups or grant table-level access as a shortcut.

## 4. Proposed read-only API contract (not deployed)

Suggested endpoint: `GET /ops/v1/summary`

Response fields should be aggregate-only:

- `generated_at`: server timestamp.
- `environment`: fixed identifier such as `supabase-staging`.
- `queue`: queue length and visible length.
- `tasks`: counts grouped by status and bounded retry aggregates.
- `latency_seconds`: completed-task count, average, median, P95 and maximum.
- `leases`: active and expired lease counts.
- `events`: counts grouped by event type, without event payloads.
- `groups`: group count, expected/linked child counts, empty-group count, token-hash mismatch count.
- `cron`: schedule, active flag, success/failure counts and latest run timestamp/duration. Never return the SQL command or command output.

Response must not contain task IDs, group IDs, user questions, query text, result content, raw capability tokens, token hashes, worker credentials, SQL, headers, or database connection information.

The API should use fixed parameterized aggregate queries or a narrowly scoped read-only database function. It must not accept arbitrary SQL, table names, filters, task IDs, or user-supplied query fragments. It should apply a short timeout, bounded response size, `Cache-Control: no-store`, and explicit environment tagging.

## 5. Proposed dashboard sections

1. **Environment and service health:** separate Vercel Production and Supabase Staging status; do not merge their health indicators.
2. **Queue:** pending/visible depth, task status counts, retry profile.
3. **Worker:** active/expired leases and last successful Cron execution.
4. **Performance:** end-to-end latency percentiles, explicitly labelled as queue wait plus provider latency.
5. **Security:** public-query screening outcomes as aggregate counts only; capability-hash consistency count; never show token material.
6. **Research integrations:** Crossref status and inference toggle state. Report `INFERENCE_ENABLED=false` and `FLYBRAIN_OPENROUTER_ENABLED=false` as disabled, not as a provider outage.
7. **Recent operational history:** bounded aggregate run outcomes only, no SQL command or message contents.

No mutation buttons belong in the first version. Retry, cancel, requeue, deployment, token rotation, and configuration changes remain outside this read-only console.

## 6. Acceptance gates before implementation

- [ ] Choose and verify an owner-only authentication model.
- [ ] Confirm the exact owner identity/UUID from an authenticated source; do not infer it from a username or email.
- [ ] Review every aggregate query against current grants and RLS.
- [ ] Prove unauthenticated requests return 401/403.
- [ ] Prove a non-allowlisted authenticated user returns 403.
- [ ] Prove the authorized owner receives aggregate-only data.
- [ ] Assert response schema contains none of the prohibited fields listed above.
- [ ] Verify no service-role or worker secret appears in client bundles, logs, Git history, or responses.
- [ ] Run tests against Staging only, then review rollback and deployment plan.
- [ ] Obtain explicit approval before deploying a new endpoint or changing database privileges.

## 7. FlyBrain's differentiation — evidence-based positioning

FlyBrain should be described as a **research orchestration and evidence-management layer**, not as a replacement foundation model.

Its potential differentiators are architectural:

- **Project-grounded retrieval:** returns source-labelled excerpts from the FlyBrain-NOS and URCAL project corpus, allowing a connected language model to synthesize against identifiable project material.
- **Tool and policy boundaries:** separates read-only retrieval, public literature search, task submission, worker execution, and private status access.
- **Provider-neutral orchestration:** URCAL/ModelHub is designed to coordinate explicitly configured providers under policy and quota controls. This is an architectural capability; it is not proof that multiple providers are currently active.
- **Auditable asynchronous research path:** the Staging pipeline has a real MCP → queue → worker → Crossref → status path, capability-token access control, query screening at both MCP and worker boundaries, and aggregate operational telemetry.

What is live today is narrower than the full vision: Staging Crossref task execution is verified; OpenRouter inference is disabled; the Vercel public MCP gateway performs source retrieval/public HTTP research; the proposed deterministic multi-agent workflow remains mock-only. No verified benchmark currently establishes better answer quality, reasoning, speed, or scientific accuracy than ChatGPT, Claude, or Gemini. Those comparisons require a controlled evaluation set and reproducible metrics.

## 8. Change log

This document records the architecture audit and a safe implementation path only. It does not change the running system, create a new Edge Function, modify database grants or policies, deploy Vercel/Cloudflare resources, merge branches, or touch Production.
