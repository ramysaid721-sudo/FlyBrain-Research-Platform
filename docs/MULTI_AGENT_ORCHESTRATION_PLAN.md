# Multi-Agent Orchestration — Staging Design

**Status:** Architecture proposal only. No agent API calls, provider activation, deployment, or production changes are implemented by this document.

## 1. Objective

Create a controlled FlyBrain orchestration layer that can distribute a research or engineering task to independent model providers, collect their outputs, compare disagreements, and produce an auditable synthesis.

The system must distinguish three separate capabilities:

1. **Provider connectivity:** a server-side adapter can reach a provider.
2. **Agent execution:** a provider has actually completed an assigned task.
3. **Multi-agent orchestration:** FlyBrain has assigned, tracked, collected, and evaluated multiple independent executions.

A configured API key alone proves none of these capabilities.

## 2. Proposed role allocation

| Role | Candidate | Primary responsibility |
|---|---|---|
| Orchestrator / integrator | FlyBrain + ChatGPT | Decompose tasks, enforce policy, synthesize evidence, verify acceptance criteria |
| Implementation worker | xAI Grok | Repository exploration, isolated implementation proposals, independent code review |
| Independent reviewer | Google Gemini | Review code and technical documents, generate edge cases, inspect explicitly approved non-sensitive material |
| Optional specialist | Other approved providers | Narrow, explicitly scoped tasks when cost and data policy permit |

These are proposed assignments, not active agent sessions. No direct model-to-model communication is assumed. FlyBrain should exchange task envelopes and results through its own ledger.

## 3. Execution topology

Use a hub-and-spoke design. Each agent receives a bounded task from the orchestrator and returns a structured result. Agents do not receive each other's credentials or direct tool permissions.

```text
User request
    |
    v
FlyBrain Orchestrator
    |
    +---- Policy / Cost / Data Gate
    |
    +---- Task Ledger
    |
    +---- Grok adapter ------> implementation/review result
    |
    +---- Gemini adapter ----> independent review/test cases
    |
    +---- ChatGPT synthesis -> comparison and acceptance decision
    |
    v
Validated result + evidence + audit trail
```

The first implementation should support sequential execution and bounded parallel fan-out. Parallelism must be configurable and conservative; do not launch unbounded model calls.

## 4. Task envelope

Every assignment should be represented by a versioned, schema-validated task envelope with at least:

- `task_id`: opaque unique identifier.
- `parent_task_id`: optional parent for decomposed work.
- `project_id` and `repository_ref`: explicit project and immutable branch/commit context.
- `role`: planner, implementer, reviewer, tester, or synthesizer.
- `provider_id` and `model_id`: allowlisted identifiers, never arbitrary caller-controlled endpoints.
- `objective`, `input_refs`, and `acceptance_criteria`.
- `data_classification`: public, internal, confidential, or prohibited.
- `cost_policy`: hard maximum spend of zero for the current project mode.
- `deadline`, `max_attempts`, and `max_output_bytes`.
- `status`, timestamps, and an idempotency key.

Task inputs should use immutable repository commit references or approved artifact IDs, not mutable branch names alone.

## 5. State machine

Allowed transitions:

- `queued -> policy_denied`
- `queued -> ready`
- `ready -> running`
- `running -> completed`
- `running -> failed`
- `running -> timed_out`
- `failed|timed_out -> retry_queued` only when retry policy allows
- `completed -> reviewed`
- `reviewed -> accepted|rejected`

Terminal states must not be silently reopened. Retries create new attempt records linked to the original task. Each transition is appended to an audit log; status is not inferred from model prose.

## 6. Shared task ledger

The ledger should separate mutable task summaries from append-only events and provider attempts.

Suggested logical records:

- `agent_tasks`: task envelope, owner, current state, policy decision, timestamps.
- `agent_attempts`: provider/model, attempt number, start/end, outcome, bounded token/usage metadata where available, and sanitized error category.
- `agent_artifacts`: output references, content hashes, media types, and classification.
- `agent_events`: append-only state transitions, approvals, policy denials, retries, and reviewer decisions.

Storage choice:
- Local development may use SQLite.
- Staging may use the existing Supabase Postgres project only after confirming available quota, access controls, retention, and that no paid tier is required.
- Do not treat a serverless function's temporary filesystem as a durable shared ledger.
- Do not store raw API keys, passwords, full private prompts, or unredacted provider errors in the ledger.

## 7. Provider adapter contract

Each provider adapter should expose a narrow interface:

- `capabilities()`: static supported features and declared data handling.
- `validate_request(task)`: schema, model allowlist, size and policy checks.
- `estimate_cost(task)`: conservative estimate; unknown must fail closed.
- `execute(task, timeout)`: bounded call returning a normalized result.
- `normalize_result(response)`: validate output shape and strip unsafe metadata.

Provider-specific secrets are fetched server-side from the approved secret vault at execution time. Secret values must never enter task envelopes, model prompts, logs, artifacts, browser code, or API responses.

The Grok adapter must use xAI's provider identity and endpoint. GroqCloud is a separate provider and must never be labelled as Grok. Gemini and xAI adapters remain disabled until exact-model pricing, quota, account eligibility, data-use terms, and zero-cost admission are independently verified.

## 8. Zero-cost admission and fail-closed policy

The current operating constraint is zero financial cost.

Before any live provider request:
1. Identify the exact provider, model, API product, region, and request features.
2. Verify current official pricing and the account's applicable free quota.
3. Require trusted server-side evidence with provenance and freshness. Caller-supplied booleans or prices are not authoritative.
4. Reject NaN, infinity, negative prices, stale evidence, ambiguous quotas, and unknown usage costs.
5. Disable paid fallback, automatic model switching, and billing-dependent features.
6. Enforce a hard maximum spend of zero before and during execution.
7. If any check is unavailable, deny the request without contacting the provider.

A provider key stored in Vault is not proof of free quota or permission to make a request.

## 9. Data protection and tool isolation

- Default classification is internal; external transfer is denied unless the task is explicitly approved for that provider.
- Only public, non-sensitive test data may be sent while provider data-use terms and retention are not fully assessed.
- Never send secrets, private research, personal records, or repository credentials to external models.
- Model outputs are untrusted data. They cannot authorize tool calls, reveal secrets, approve deployments, or change policy.
- Agent workers receive no general-purpose GitHub, Supabase, deployment, or browser credentials.
- Code changes are proposed through isolated branches and pull requests. Do not let multiple agents edit the same file concurrently.
- Side effects, publication, external messages, purchases, billing changes, production operations, and destructive actions require explicit human approval.

## 10. Cross-review and acceptance

For code tasks:
1. One worker proposes changes on a dedicated branch.
2. A different provider reviews the immutable commit diff, not the worker's summary alone.
3. A test runner executes deterministic tests.
4. The orchestrator compares findings against acceptance criteria and resolves disagreements with evidence.
5. A human reviews the final PR before merge or deployment.

For research tasks:
1. Assign independent evidence-gathering subtasks.
2. Require source URLs, publication dates, and claim-to-source mapping.
3. Detect contradictory findings and missing evidence.
4. Separate source facts, model interpretations, and unresolved hypotheses.
5. Produce a synthesis with confidence and provenance.

Agreement between models is not itself proof of correctness.

## 11. Operational rollout gates

| Stage | Deliverable | Activation condition |
|---|---|---|
| 0 | This design and threat model | Documentation review |
| 1 | Local mock adapters and schema tests | Offline tests pass |
| 2 | Ledger schema and local deterministic executor | Isolation and state-transition tests pass |
| 3 | Provider adapters in disabled mode | Static security review; no live calls |
| 4 | Free-tier admission verifier | Trusted, fresh, model-specific evidence; otherwise remain disabled |
| 5 | Controlled staging execution | Explicit approval, public test data, zero-cost gate |
| 6 | Cross-provider review and audit | Reproducible task and attempt records |
| 7 | Production consideration | Separate security, cost, privacy, and human approval; outside current scope |

## 12. Current verified baseline

- The repository has a Vercel MCP bridge and a model-consultation layer in the packaged release.
- The bridge uses a model-provider abstraction; the complete packaged source must be inspected before adding a second orchestration runtime.
- The repository documentation describes persistent task registry and bounded parallel browser workflows as planned capabilities, not completed features.
- The Gemini mock PR is separate and remains draft-only.
- No verified live Grok or Gemini agent session is currently connected to this project.
- Current project policy keeps live inference disabled and prohibits paid usage.

## 13. Explicit non-goals

This proposal does not create provider credentials, send prompts to Grok or Gemini, provision new services, add billing, change production, merge branches, or enable inference. It is an implementation blueprint and acceptance contract only.


## 14. Verified packaged architecture — avoid duplicating existing components

The repository's committed `FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip` was inspected directly. It already contains:

- `components/FlyBrain-NOS/flybrain_os/model_hub.py`: `Provider`, `discover_providers()`, `task_plan()`, `ModelConsultation`, `check_provider()`, and concurrent provider calls.
- `components/FlyBrain-NOS/tests/test_model_hub.py`: tests for provider discovery, role planning, parallel consultation, xAI request construction, Gemini-compatible provider discovery, local-only filtering, and metadata probes.
- `components/URCAL/urcal/queue.py`: `InMemoryQueue` and a SQLite-backed leased queue with acknowledgement, retry, and dead-letter states.
- `components/FlyBrain-NOS/docs/MULTI_MODEL_HUB.md`: the existing operator guide.

**Implementation decision:** extend and harden the existing ModelHub + URCAL queue. Do not introduce a second model hub, a competing queue, or a second provider registry.

### 14.1 What is already implemented

- xAI is a distinct provider preset (`xai`, `https://api.x.ai/v1`) and is not the same as Groq (`groq`).
- Gemini has its own OpenAI-compatible provider preset.
- `ModelConsultation.consult()` can submit bounded concurrent calls and write provider/model/role/status/response/error records to a local SQLite database.
- `URCAL.SQLiteQueue` supports durable local task claiming across local processes, lease expiry, acknowledgement, retry, and dead-lettering. Its documented delivery model is at-least-once, not exactly-once.
- `task_plan()` can describe proposer, independent critic, domain reviewer, and synthesizer roles without contacting a model.

These are code capabilities in the packaged archive. They do not establish that any provider is currently configured, reachable, free, or enabled in the deployed FlyBrain service.

### 14.2 Gaps to resolve before live multi-agent execution

1. **No actual result-to-synthesizer handoff:** the current consultation assigns roles based on provider-list position. Its synthesizer prompt is an independent analysis of the original task; it does not receive and synthesize the proposer and critic outputs. The returned plan is descriptive, not an executed dependency graph.
2. **No hard zero-cost admission gate:** provider discovery and consultation do not enforce a trusted model-specific free-quota proof or a hard maximum spend of zero. A configured remote provider can incur charges.
3. **Environment-variable credential model:** the packaged module reads credentials from process environment variables. A production integration must use the approved server-side Vault retrieval path and must never expose values to prompts, logs, browser clients, or task records.
4. **External data transfer:** remote providers receive the task prompt. The `local_only` filter is useful but only restricts to providers explicitly marked local; it does not make remote calls safe or free.
5. **Error persistence boundary:** `ModelConsultation.consult()` persists `str(exception)` for a failed caller. Production callers must normalize errors to allowlisted categories before persistence; never persist arbitrary exception text.
6. **Ledger scope:** the consultation SQLite table stores consultation outputs, but it is not a full task ledger with immutable task envelopes, attempt identities, append-only transition events, reviewer decisions, and artifact hashes.
7. **Queue scope:** URCAL's SQLite queue is a local durable queue, not a cross-host distributed broker. Its at-least-once delivery requires idempotent workers and explicit acknowledgement/nack handling.
8. **Metadata probe limits:** `check_provider()` requests `/models`. A reachable model-list endpoint is not evidence of remaining free quota, effective request price, or successful generation.
9. **Role assignment:** assigning roles by provider list index is not a reliable policy. Role-to-provider mapping must be explicit, validated, and recorded in each attempt.
10. **Concurrency and timeouts:** the current consultation caps its worker pool at six, but production orchestration still needs a global budget, cancellation/deadline propagation, bounded retries, and idempotency.

### 14.3 Recommended implementation sequence

1. Add a no-network dry-run planner that validates explicit provider-role assignments and creates immutable task/attempt envelopes.
2. Reuse URCAL's queue contract for local mock-only execution; do not enable remote providers.
3. Add a structured result handoff: proposer output -> independent critic review -> synthesizer receives both outputs plus the original task and must preserve disagreements.
4. Add a policy gate before provider discovery/execution. Default-deny all remote calls; require trusted, fresh, model-specific zero-cost evidence before any future external request.
5. Replace arbitrary exception persistence with sanitized error codes and add output-size limits, idempotency, and append-only events.
6. Add tests for state transitions, duplicate task IDs with conflicting payloads, expired leases, worker acknowledgement, role assignment, synthesis inputs, secret redaction, and zero-cost denial.
7. Only after offline tests and a separate security review should any staging provider call be considered. The current project authorization still prohibits paid calls and does not permit inference activation by this plan.

Until these gaps are addressed, the correct status is **multi-provider orchestration foundation exists; production-safe multi-agent workflow is not yet complete**.
