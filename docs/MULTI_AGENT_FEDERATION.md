# FlyBrain Multi-Agent Federation — Staging Design

Status: design proposal only. This document does not deploy agents, provision compute, grant credentials, or enable outbound model calls.

## Objective

Evolve FlyBrain from a single scheduled worker into a governed multi-agent coordinator that can delegate independent work to authorized agents and service-native bots across providers, while preserving the public-data-only model policy and strict zero-cost admission rule.

## Interoperability model

Use two complementary interfaces:

- **A2A (Agent2Agent)** for task delegation between independently hosted agents. Discover remote capabilities through an Agent Card; submit a bounded task; poll/subscribe for task state and retrieve artifacts. Treat every remote agent as an untrusted external executor.
- **MCP (Model Context Protocol)** for deterministic tools, data sources, and service operations exposed by a platform. Discover only the specific toolsets required for a task; do not grant blanket access.

A2A is the preferred peer-agent task protocol; MCP is the preferred tool interface. A provider may expose one, both, or neither. For services without either interface, use only their documented APIs or user-authorized automation surfaces. Do not scrape private control planes or bypass product restrictions.

## Proposed topology

1. **FlyBrain Coordinator** — decomposes work, selects agents, assigns deadlines, and aggregates results.
2. **Agent Directory** — stores public Agent Card metadata, provider identity, declared skills, endpoint, supported protocol, and last successful health check. No credentials or private prompts.
3. **Policy Gateway** — validates task scope, public-data classification, destination allowlist, cost evidence, quotas, payload screening, and output size before dispatch.
4. **Specialist agents** — optional workers for code review, test design, documentation, research, and infrastructure diagnostics.
5. **Result verifier** — checks artifacts against acceptance criteria and runs deterministic tests before marking tasks complete.
6. **Supabase queue and scheduler** — remains the durable task ledger, lease manager, retry coordinator, and watchdog. Remote agent task IDs are recorded for reconciliation.

## Admission rules

A remote agent may receive a task only if all conditions are satisfied:

- Its endpoint and identity are verified and explicitly allowlisted.
- The task is within the agent's advertised capability and authorized scope.
- The exact outbound payload is classified as public using trusted provenance; caller-supplied flags alone are insufficient.
- The public-only metadata guard and conservative content scanner run on the final serialized payload immediately before dispatch.
- No credentials, API keys, tokens, private source code, personal data, customer data, or operational secrets are included.
- Provider price is explicitly USD 0, free capacity is positively verified, and quota evidence is fresh. Unknown pricing or capacity means reject.
- Request size, concurrency, timeout, retry count, and total task budget are bounded.
- The remote agent's output is treated as untrusted input and screened before it can trigger another tool or agent.

No external model is activated by this design. Provider terms on retention and model training must be reviewed before any public payload is sent.

## Delegation protocol

For each task, the coordinator sends a minimal task envelope:

- opaque task ID and idempotency key;
- task objective, acceptance criteria, deadline, and maximum output size;
- only the minimum public context required;
- explicit prohibition on secrets, private data, unauthorized network access, and onward delegation unless separately permitted.

The coordinator stores remote task ID, provider, timestamps, quota evidence, status, and a hash of the request/artifact for reconciliation. It does not store unnecessary copies of full prompts or artifacts.

## Storage, encryption, and cleanup

- Use HTTPS/TLS for all remote calls; reject plaintext endpoints.
- Use platform-managed encryption at rest for persistent stores. Where application-level encryption is required, use envelope encryption with keys held by the platform's secret manager/KMS, never committed to Git or embedded in task payloads.
- Do not persist model prompts or full remote outputs by default. Persist only task metadata, hashes, acceptance results, and the smallest artifact needed for reproducibility.
- Use ephemeral working directories and object storage with short lifecycle TTLs for intermediate artifacts. Delete temporary artifacts after verified completion or expiry.
- Keep minimal security/audit records required for accountability and incident investigation. Do not disable, evade, or erase provider audit logs; cloud providers may retain their own logs and backups beyond FlyBrain's control.
- Encryption at rest does not hide data from a provider while a worker is actively processing it. Only send public data under the current policy.

## Failure handling

- Use lease fencing and idempotency keys to prevent duplicate side effects.
- A timed-out remote task is not assumed failed; query its task state before retrying.
- Retry only transient failures with bounded exponential backoff.
- Quarantine repeated failures and malformed or policy-violating outputs.
- If a provider's free quota, pricing, or data policy cannot be verified, disable that provider automatically.
- Never fall back silently to a paid endpoint.

## Rollout gates

1. Add a read-only A2A Agent Card discovery/parser and MCP capability inventory.
2. Add an allowlisted agent registry with schema validation and health/quota timestamps.
3. Implement a no-network dry-run planner that displays delegation decisions and estimated resource use.
4. Add policy-gateway tests for endpoint allowlists, public provenance, payload scanning, cost=0, quota freshness, timeouts, output screening, and denial cases.
5. Add one opt-in remote-agent adapter only after a compatible endpoint and its free quota/privacy terms are verified.
6. Run staging fault-injection tests for retries, duplicate delivery, provider outage, and artifact expiry.
7. Require review and verified CI before any production deployment.

## Current limitations

- No A2A Agent Registry or remote A2A endpoint is currently configured in this FlyBrain project.
- Existing connected integrations expose service tools and browser automation, but they are not automatically autonomous peer agents and cannot be assumed to accept delegated work.
- ChatGPT's hosted model weights, private runtime, internal prompts, and identity cannot be copied to third-party servers. FlyBrain can host its own coordinator code and use separately licensed models or agents where permitted.
- This document is a staging design. It does not claim multi-agent execution, persistent background reasoning, or cross-cloud compute is active.
