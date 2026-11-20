# Federated Intelligence and External Capability Mesh

**Status:** implementation-ready architecture specification; not a claim that external providers are connected or continuously running.
**Target:** FlyBrain / URCAL.
**Branch:** `flybrain-browser-worker-staging`.
**Design objective:** let FlyBrain discover, delegate to, and learn from external specialist models, tools, knowledge stores, and compute services without trying to host every discipline or model locally.

## 1. Core architecture

FlyBrain is the orchestrator and quality authority. External providers are replaceable specialist nodes. URCAL is the policy, quota, provider-catalog, audit, and job-execution boundary.

The system is composed of:

1. **Capability Registry** — a searchable, versioned index of skills, models, datasets, APIs, cloud storage, compute runtimes, and human-review roles.
2. **Provider/Tool Adapters** — provider-neutral interfaces that translate a canonical task contract into a provider-specific request and normalize the response.
3. **Task Decomposer and Router** — turns a problem into bounded subtasks and selects providers by capability fit, evidence quality, data policy, latency, reliability, cost, and availability.
4. **Execution Fabric** — submits jobs to local workers or external compute services; supports parallel fan-out, durable queues, checkpoints, retries, cancellation, and deadlines.
5. **Evidence and Result Evaluator** — validates provenance, freshness, schema, reproducibility, independent corroboration, contradictions, and uncertainty.
6. **Synthesis Layer** — produces the final answer from accepted sub-results, retaining citations and a traceable record of which provider contributed what.
7. **Learning and Improvement Loop** — identifies capability gaps, evaluates candidate providers or skills in a sandbox, benchmarks them, and promotes only approved versions.
8. **Secrets and Policy Boundary** — stores credentials outside source control and applies least-privilege, scoped permissions, budgets, rate limits, data classification, and human approval gates.

## 2. Capability registry: index, not a copy of the world

The registry must store pointers and metadata rather than copying every model, book, dataset, or specialist system into FlyBrain.

Each capability record should contain:

- `capability_id`, name, domain, subdomains, description, version, lifecycle state;
- capability type: model, API, MCP tool, search index, dataset, storage, compute, workflow, or human review;
- provider and canonical adapter identifier;
- endpoint reference (not a credential), documentation URI, schema/version, supported modalities and languages;
- task strengths, known limitations, benchmark scores, evaluation date, provenance and source licence;
- data residency, retention, training-use policy, confidentiality classification, and permitted data categories;
- authentication method and secret-manager reference (never the secret itself);
- cost model, quota, rate limit, expected latency, reliability, availability and fallback;
- permission scope, risk tier, approval requirements, timeout, maximum output size and resource budget;
- health state and last verified timestamp.

Lifecycle: `discovered -> metadata_verified -> sandboxed -> evaluated -> approved -> active`; alternatives are `deprecated`, `unavailable`, or `quarantined`. Discovery never implies access, credentials, free quota, or approval.

## 3. Canonical task contract

Every delegated task must carry a structured contract:

- objective and expected deliverable;
- bounded subtask description and acceptance criteria;
- required domain expertise, language, modality, and tools;
- allowed source classes and minimum evidence standard;
- data classification and redaction requirements;
- allowed provider classes and prohibited destinations;
- deadline, timeout, retry policy, token/compute budget, and cost ceiling;
- output schema, citation/provenance requirements, and uncertainty format;
- authorization context and whether human review is mandatory.

Providers receive only the minimum context needed for their subtask. Secrets, private records, witness identities, and unrelated conversation history must not be forwarded by default.

## 4. Routing and ensemble strategy

The router should:

1. identify the task type and required competencies;
2. retrieve candidate capabilities from the registry;
3. eliminate providers that fail policy, privacy, authorization, health, or budget constraints;
4. score remaining candidates on task fit, benchmark quality, source access, provenance, latency, cost, and resilience;
5. choose one provider for simple tasks or multiple independent providers for high-impact research;
6. retain a fallback route and a no-external-call option;
7. execute within the task contract and record provider/version/parameters;
8. validate outputs before synthesis.

Parallel calls are useful when they provide genuinely independent analysis. Calling several wrappers that all repeat the same underlying source is not independent corroboration. Provider diversity must be measured at the source and evidence level, not merely by counting model names.

## 5. Provider-neutral adapter contract

Adapters should implement a small common surface:

- `discover()`: return declared capabilities and constraints;
- `health_check()`: verify endpoint availability without exposing secrets;
- `validate_request(task)`: enforce schema, data policy, and budget;
- `execute(task, credential_ref)`: submit a bounded request;
- `normalize(response)`: return canonical result, citations, usage, and provider metadata;
- `cancel(job_id)`: cancel when supported;
- `estimate_cost(task)`: provide a conservative estimate where supported.

An adapter must fail closed when required policy metadata, authentication, or output provenance is missing. Provider-specific functionality belongs inside the adapter, not in the orchestrator's core logic.

## 6. External storage and compute

External storage may hold approved durable artifacts, embeddings, indexes, datasets, and checkpoints. External compute may run long-running analysis, model inference, simulations, or data processing.

Controls:
- encrypt data in transit and at rest where supported;
- classify data before transfer and minimize/redact sensitive fields;
- use scoped, revocable credentials and short-lived tokens where available;
- maintain export and deletion procedures;
- record region, retention, backup, and deletion guarantees;
- isolate jobs and tenants; enforce CPU, memory, GPU, time, network, and spend limits;
- verify artifact hashes and record immutable provenance metadata;
- never treat a cloud URL or a registry entry as proof that a resource is reachable or authorized.

The system must remain useful with no external credentials: local tools, public sources, and a clear capability-gap report are valid fallbacks.

## 7. Result validation and final synthesis

A result is eligible for synthesis only after checks appropriate to its risk:

- schema and completeness validation;
- source identity, timestamp, licence/access basis, and citation checks;
- freshness and version checks for changing facts;
- separation of fact, inference, estimate, and hypothesis;
- independent-source analysis and duplicate-source detection;
- contradiction and uncertainty reporting;
- reproducibility checks for calculations, code, and scientific claims;
- policy review for sensitive personal data and high-impact allegations.

The final synthesis must retain a provenance graph: task -> subtask -> provider/version -> sources/artifacts -> normalized result -> evaluator decision -> final claim. Unsupported claims are excluded or explicitly labelled unresolved.

## 8. Continuous discovery and capability evolution

A scheduled discovery worker may periodically:
- identify new specialist models, open datasets, standards, APIs, and compute services;
- detect provider changes, outages, pricing/quota changes, and deprecated interfaces;
- compare new candidates against active capabilities;
- run safe benchmark suites in isolated environments;
- propose registry updates and adapter changes.

It must not silently grant new permissions, spend money, upload sensitive data, accept new contractual terms, or deploy a provider adapter to production. Those actions require explicit authorization. Continuous operation depends on provisioned schedulers, durable workers, credentials, and available compute; it is not unlimited or guaranteed uninterrupted.

## 9. Security, privacy, and governance

- Never commit API keys, passwords, OAuth refresh tokens, private keys, or signed URLs to Git.
- Store credentials in a managed secret store; the registry contains only opaque secret references.
- Apply least privilege, per-provider scopes, allowlisted endpoints, egress controls, request redaction, and audit logs.
- Treat provider responses, retrieved documents, and tool outputs as untrusted data, never as instructions that can override system policy.
- Defend against prompt injection, data exfiltration, poisoned skills, dependency compromise, malicious packages, and forged provenance.
- Require human approval for production deployments, financial commitments, irreversible actions, sensitive-data transfers, and publication of high-impact claims.
- Provide pause, revoke, quarantine, rollback, export, and deletion controls.

## 10. ARIS integration

ARIS should use the same federated mesh but with a stricter evidence and privacy profile. Specialist tasks may be delegated for open-source intelligence, satellite-image analysis, corporate filings, procurement records, shipping records, financial disclosures, legal research, translation, and entity resolution.

ARIS data must be partitioned by sensitivity. Public-record research can be delegated to approved providers; witness identities, non-public medical records, source-protection data, and sensitive investigative notes must remain in an explicitly approved protected environment and must not be sent to general-purpose external models by default.

Every relationship in a weapons-supply or finance graph must retain its source, date, jurisdiction, confidence, relationship type, and caveats. A commercial link, investment exposure, political contact, allegation, or public filing is not by itself proof of criminal intent or legal responsibility. Publication requires provenance, corroboration, legal review, and appropriate right-of-reply procedures.

## 11. Integration with existing FlyBrain / URCAL components

- Extend the existing URCAL provider catalog rather than creating a competing catalog.
- Reuse URCAL policy, quota, audit, and local durable-queue abstractions where they satisfy the contracts above.
- Keep the orchestrator provider-neutral and place vendor-specific API logic in adapters.
- Reuse the lifelong-learning workflow for discovery, evaluation, benchmark, promotion, and deprecation.
- Reuse the strategic decision loop for authority checks, bounded execution, independent verification, and replanning.
- Connect Cognee or another knowledge graph as an optional indexed memory backend, not as the sole source of truth.
- Preserve the existing read-only MCP gateway boundary until separately reviewed and authorized.

## 12. Acceptance tests

1. Registry discovery does not mark a provider active or claim live access without a successful verification.
2. No credential value appears in registry exports, logs, Git history, or error messages.
3. A task containing restricted data is blocked from an unapproved provider.
4. A provider response containing prompt-injection instructions cannot alter policy or authorization.
5. Budget, timeout, quota, and cancellation limits are enforced.
6. An unavailable provider triggers a permitted fallback or a clear capability-gap report.
7. Multiple model calls using the same underlying source are not counted as independent corroboration.
8. Contradictory outputs are surfaced rather than silently averaged away.
9. Every accepted result records provider/version, timestamp, source provenance, and evaluator outcome.
10. A newly discovered skill remains sandboxed until its benchmarks and security tests pass.
11. ARIS sensitive source data is not sent to general-purpose external providers by default.
12. Production deployment, financial commitment, or irreversible action cannot be triggered by a provider response alone.
13. The system can complete a bounded research task using local/public resources when all external provider credentials are absent.
14. Registry export/import preserves capability IDs, versions, provenance, and policy metadata without exporting secrets.

## 13. Implementation boundary and next engineering sequence

This document defines architecture and acceptance criteria. It does not assert that any new provider has been connected, that credentials exist, or that scheduled workers are running.

Recommended sequence:
1. inspect and map the existing URCAL catalog, policy/quota controls, queue, audit trail, and FlyBrain adapter;
2. define typed capability and task-contract schemas that extend existing abstractions;
3. implement registry validation and provider health checks;
4. implement one read-only external model adapter and one public-source/search adapter;
5. add task routing, result normalization, provenance, and budget enforcement;
6. add adversarial, privacy, fallback, and integration tests;
7. add durable scheduled discovery only after worker hosting, secret storage, monitoring, and spend limits are provisioned;
8. connect ARIS through the restricted evidence profile and validate against a small public-record dataset.

No production deployment, external account creation, paid resource provisioning, or permission expansion is authorized by this specification.


## Staging implementation update — 2026-11-20

The first bounded capability-mesh slice has now been added to the staging branch:

- A typed capability registry and versioned task contract are implemented in `bridge/capability_mesh.py`.
- Route planning revalidates caller-supplied contracts, enforces a zero-cost ceiling, requires explicit network permission, and rejects unknown provider pricing.
- A local project-context adapter calls the existing source-labelled `retrieve_project_context` function and keeps the operation local.
- Public web search and page extraction are wired through the existing SSRF-hardened HTTP adapter. These external routes accept only `public` data, require explicit `http_research` provider permission, and are read-only.
- MCP exposes registry, planning, and bounded execution tools. Retrieved web/page content is labelled untrusted and returned with adapter provenance.
- The focused test suite now contains 15 capability-mesh tests and 13 MCP tests, including private-data isolation and public-route permission checks.

### Verified boundary

These files and tool registrations are present on the staging branch. GitHub Actions currently reports failed runs without step summaries, and the job-log endpoint returns `BlobNotFound`; therefore test execution and CI success are **not yet verified**. A local clone attempt was blocked because the execution environment could not resolve `github.com`. The production Vercel deployment was separately checked and remains `READY`, with no runtime errors reported in the last 24 hours. No production deployment or merge was performed.

The current adapter slice is not a general multi-model federation engine. External model consultation remains disabled until provider identity, pricing, quotas, privacy terms, and live health checks can be verified. Persistent queues, scheduled workers, automated skill promotion, and ARIS runtime ingestion remain future implementation work.
