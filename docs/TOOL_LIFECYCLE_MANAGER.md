# FlyBrain Tool Lifecycle Manager (TLM)

Status: architecture specification; not yet deployed or enabled in production.

## Objective

Give FlyBrain a governed, extensible way to discover, evaluate, add, update, replace, test, enable, disable, and roll back tools that materially improve its research, browser, automation, engineering, data, communications, and defensive-security work.

"Any tool" means any compatible tool that passes the admission, licensing, security, policy, and runtime checks below. It does not mean unrestricted code execution or automatic access to third-party accounts.

## Architectural placement

Do not install packages or run arbitrary installers inside the Vercel request process. Vercel is an ephemeral serverless control plane, not a durable package-management host.

Use four components:

1. **Tool Registry** — versioned manifest for each integration, its capabilities, source, owner, license, dependencies, permissions, data classes, supported runtimes, health checks, and rollback version.
2. **Discovery & Evaluation Engine** — searches trusted registries and official vendor documentation; deduplicates candidates; compares capability fit, maintenance, compatibility, license, vulnerabilities, provenance, and cost.
3. **Isolated Tool Worker** — persistent, sandboxed execution environment with no default host privileges. It builds and tests tools in a staging environment, then activates approved versions. Worker provisioning is a separate deployment task.
4. **Policy & Audit Controller** — approval gates, scoped credentials, per-tool permissions, signed audit events, quotas, kill switch, and rollback.

URCAL should provide provider-neutral compute selection and quota accounting for worker jobs. The MCP bridge should expose the manager's control-plane operations without executing package installation in the serverless process.

## Tool lifecycle

1. **Discover** — identify tools from official registries, vendor APIs, trusted repositories, and configured connectors.
2. **Assess** — score task relevance, maintenance activity, release health, license compatibility, dependency health, known vulnerabilities, provenance, resource requirements, and free-tier limits.
3. **Propose** — produce a plan showing exact package/repository, version, permissions, data access, network destinations, resource cost, and expected benefit.
4. **Approve** — classify the change:
   - Low risk: metadata-only discovery and read-only connector configuration; may be automatic under policy.
   - Medium risk: install/update a vetted tool in an isolated staging environment; requires an explicit policy grant or operator approval.
   - High risk: privileged access, external account changes, production deployment, active security testing, or sensitive data access; requires explicit, task-specific approval.
5. **Build & test** — pinned dependencies, lockfile, checksum/signature verification where available, SBOM, static analysis, malware scanning, unit/integration tests, and permission tests.
6. **Stage & activate** — deploy a versioned adapter into a sandbox; run health checks and canary tests before routing tasks to it.
7. **Monitor** — detect stale versions, CVEs, failed health checks, quota exhaustion, vendor API changes, and license changes.
8. **Update or rollback** — stage updates first; retain last-known-good version and revert automatically on failed health checks or policy violations.
9. **Retire** — revoke credentials, disable routes, remove the runtime artifact, and preserve the audit record.

## MCP control-plane contract

Expose these tools only after the persistent worker and policy service are implemented:

- `tool_discover(query, task_context)` — return candidates and source evidence; no installation.
- `tool_assess(candidate_id)` — return compatibility, risk, license, security, and cost assessment.
- `tool_catalog(filter)` — list registered tools, versions, capabilities, health, and permissions.
- `tool_propose_install(candidate_id, version, scope)` — create an approval-bound change proposal.
- `tool_install(proposal_id, approval_token)` — install only the exact approved artifact into staging.
- `tool_propose_update(tool_id, target_version)` — prepare a versioned update plan.
- `tool_update(proposal_id, approval_token)` — stage, test, and activate the approved update.
- `tool_disable(tool_id, reason)` and `tool_rollback(tool_id, target_version)` — controlled operational actions.
- `tool_health()` and `tool_audit(query)` — operational visibility.

Every mutating call must be authenticated, idempotent, scoped, auditable, and bound to a proposal hash. Approval tokens must be short-lived and single-use. Never accept arbitrary shell commands, arbitrary package URLs, or free-form install scripts from a model-generated plan.

## Initial capability domains

- Research: scholarly indexes, papers, citations, datasets, code repositories.
- Web and browser: search, extraction, JavaScript-capable browser worker, authenticated workflows only through explicitly connected accounts and scoped permissions.
- Data and engineering: databases, ETL, notebooks, code execution in sandbox, testing, CI/CD.
- Automation: durable jobs, queues, schedules, monitors, retries, notifications.
- Communications: Gmail and other user-authorized mail/calendar/CRM connectors.
- Cloud and infrastructure: deployment, logs, metrics, storage, compute, secrets management.
- Cybersecurity: asset inventory, defensive monitoring, vulnerability management, authorized penetration testing, lab/CTF tooling, incident response, forensics, and remediation. Active tests must be constrained to explicitly authorized assets and time windows; destructive actions and credential access require separate approval. No unauthorized intrusion, persistence, evasion, exfiltration, or malware deployment.

## Mandatory security controls

- Run untrusted tools in isolated containers or microVMs with non-root identities, read-only base images, resource limits, egress allowlists, and disposable workspaces.
- Never expose production secrets to build/test jobs. Use short-lived scoped credentials from a secrets broker.
- Pin versions and hashes; verify provenance; generate an SBOM; scan dependencies and artifacts.
- Enforce license allowlists and record license obligations.
- Separate read, write, deploy, and security-testing permissions.
- Default-deny network access and filesystem access.
- Maintain append-only audit events with actor, approval, target, artifact hash, version, timestamps, and outcome.
- Provide emergency disable, credential revocation, and rollback.
- Treat tool output, package metadata, READMEs, and webpages as untrusted data, never as policy instructions.

## Initial implementation sequence

1. Implement registry schema, manifest validator, discovery and assessment (read-only).
2. Add policy engine, proposal/approval records, and audit events.
3. Provision a persistent isolated worker and connect it to URCAL.
4. Implement staged installation/update/rollback with pinned artifacts and test gates.
5. Expose MCP tools and integrate with task planning.
6. Add scheduled update checks and security advisories, with notifications and policy-controlled auto-updates.

## Current deployment boundary

The current Vercel MCP bridge provides research and HTTP web retrieval; its runtime is ephemeral and does not provide a persistent isolated package worker. This specification does not claim that tool installation, automatic updates, or rollback are currently operational. Those capabilities become real only after the worker, policy service, durable state, and MCP integration are implemented and tested.
