# FlyBrain Autonomous Service Ecosystem (FASE)

**Status:** staging architecture specification.
**Relationship:** extends the Unified Storage Compatibility Layer (USCL) and Federated Intelligence Capability Mesh.

## 1. Design principle

FASE emulates useful functions and interfaces, not paid entitlements, proprietary code, provider identity, or contractual privileges. It may independently reproduce a workflow through a different technical design where lawful. It must not bypass billing, quotas, authentication, rate limits, licensing terms, or access controls.

Prefer the least expensive lawful implementation that meets acceptance criteria. Cost state is known_zero, known_nonzero, or unknown; unknown is never treated as zero. No paid usage or overage without explicit authorization.

## 2. Architecture

### Service Capability Registry
A versioned catalogue of capabilities, implementations, adapters, dependencies, licence records, operational state, cost model, quotas, and acceptance tests. Discovery does not imply approval or readiness.

### Functional Requirements Extractor
Converts a requested commercial capability into neutral outcomes, inputs, outputs, constraints, and independently authored acceptance criteria. It must not ingest confidential source material or copy protected expression.

### Service Emulation Planner
Selects among original FlyBrain code, compliant open-source components, documented standards-based adapters, authorized hosted services, or a composition of smaller services. Compare coverage, correctness, security, maintenance, data policy, licence obligations, hosting requirements, and total cost.

### Clean-Room Builder and Compliance Gate
Creates independent design specifications and routes components through the FASE Clean-Room Functional Replication and IP Compliance Policy. Unreviewed, incompatible, or quarantined components cannot be promoted.

### Provider-Neutral API Facade
Expose stable internal contracts for Storage, Memory, Search, Browser, Workflow, Document, Observability, and Artifact services. Each adapter declares supported operations, data classifications, limits, cost, licence/provenance, and health status.

### Multi-Cloud Data Plane
Use USCL for provider-neutral object and file operations. Distinguish primary working store, active replica, standby replica, immutable or append-only backup, and archive. A backend is eligible only after authentication, quota, persistence, capabilities, and data policy are verified. Storage replication is not compute replication.

### Execution Plane
Run adapters and services on authorized local or hosted compute. Enforce CPU, memory, time, network, concurrency, storage, and cost budgets. Persistent state must not rely on ephemeral serverless filesystems.

### Resilience and Recovery Controller
Monitor health, validate checksums, track replication lag, detect conflicts, and run restore drills. Fail over only when the alternate backend meets data policy, integrity, and cost constraints. Otherwise stop safely and report the capability gap.

### Evaluation and Promotion Controller
Require unit, integration, security, compatibility, licence, and recovery tests before promotion. New components start discovered or sandboxed; only approved components may become active.

## 3. Service families to evaluate

Priority order:
1. Storage, file service, sync, snapshots, version history, artifact registry.
2. Knowledge and memory: metadata, graph storage, vector search, retrieval, provenance.
3. Workflow automation: durable jobs, scheduler, retries, checkpoints, cancellation, event triggers.
4. Browser automation: bounded Playwright sessions, domain allowlists, isolated contexts, explicit session authorization.
5. Document processing: PDF conversion, OCR, extraction, office formats, indexing.
6. Search and research: public-web retrieval, local document search, citations, provenance.
7. Observability: health checks, logs, metrics, traces, alert routing.
8. API gateway and tool registry: authentication, scopes, quotas, audit, schema validation.
9. Compute and model serving where hardware, licence, privacy, and total cost make self-hosting viable.

Candidate projects for evaluation include n8n, Qdrant, SQLite, Syncthing, rclone, restic, Kopia, Stirling-PDF, Prometheus, Grafana, and Playwright. These are candidates, not approved dependencies. Verify repository identity, maintenance, release provenance, licence, security advisories, dependency health, hosting requirements, and compatibility before adoption.

## 4. Multi-cloud replication model

### Logical object identity
Every object has a stable logical ID, version ID, content hash, classification, retention class, and provenance record. Provider-specific object keys are implementation details.

### Replication manifest
Record source version, destination backend, object key, checksum, size, classification, replication state, timestamp, retry count, and verification result. Never include credentials.

### Consistency and conflicts
Use optimistic concurrency and immutable version identifiers. Do not assume distributed transactions across consumer cloud drives. Detect concurrent edits and preserve both versions until a deterministic or human-approved resolution is selected.

### Deletion safety
Treat deletion as a tombstone first. Propagate it only after retention and backup checks. A backup must not mirror destructive changes in a way that destroys the last recoverable copy.

### Verification
Verify checksums after upload and restore where supported. Record replication lag and last successful restore drill. Successful upload is not proof of recoverability.

### Data placement
Route data according to classification, jurisdiction, retention, and explicit authorization. Sensitive content is not replicated to every backend by default. Encrypt before upload where appropriate and keep keys separate.

## 5. Cost and quota governance

- No paid resource creation, subscription, overage, or billable API call without explicit approval.
- Never evade quotas through account cycling, identity manipulation, or distribution across accounts to defeat limits.
- Use legitimate multi-provider redundancy only within each provider's terms and quotas.
- Reserve quota headroom for metadata, recovery, and restore operations.
- Apply request, byte, concurrency, CPU, memory, and time budgets.
- Stop when cost or quota is unknown and no safe estimate is available.
- Report free-tier constraints and operational trade-offs honestly.

## 6. Security controls

Use least-privilege scoped credentials in secret managers; classify and minimize data before transfer; encrypt in transit and at rest where supported; defend against SSRF, path traversal, archive bombs, tenant-isolation failures, and injection; authenticate internal service calls; pin dependencies and generate an SBOM; verify package provenance; keep audit logs free of secrets; sandbox untrusted components and documents; and require approval for destructive, financial, production, or external-disclosure actions.

## 7. Service lifecycle

Lifecycle: discovered -> provenance_checked -> licence_reviewed -> sandboxed -> tested -> approved -> active -> monitored -> deprecated.

Alternative states: rejected, quarantined, retired.

Every transition records actor, evidence, timestamp, version, and rationale. A new version or material change triggers re-evaluation.

## 8. Implementation sequence

1. Inventory existing URCAL abstractions, USCL status, provider credentials, quotas, and execution environments.
2. Add service capability and component compliance schemas.
3. Add a registry with fail-closed lifecycle validation.
4. Implement one low-risk service adapter and contract tests.
5. Implement USCL's first real storage adapter only after a safe backend and quota are verified.
6. Add replication manifests and a two-backend checksum/restore test.
7. Add one memory/search service composition.
8. Add workflow and browser services only after durable execution and isolation requirements are met.
9. Add monitoring, recovery drills, and operational runbooks.
10. Promote only after security, licence, cost, and reliability acceptance gates pass.

## 9. Acceptance criteria

- Every active capability has a verified implementation, provenance, licence record, cost state, and tests.
- Every third-party component passes the FASE IP compliance policy.
- A provider-neutral client can switch between two verified implementations without changing business logic.
- A real object can be written to two authorized backends and independently read back with matching checksums.
- Concurrent edits and deletions cannot silently destroy the only good copy.
- Restore drills prove backups are usable.
- Unknown cost, unknown quota, and unauthorized data transfer fail closed.
- No paid fallback or production deployment occurs without explicit authorization.
- Service health and capability status reflect observed evidence, not documentation alone.

## 10. Staging implementation update

The following bounded governance and planning slice has been added:
- Component review model and fail-closed evaluator in bridge/service_emulation_governance.py.
- Authenticated MCP tool evaluate_component_review in bridge/mcp_server.py.
- Deterministic service-emulation planner in bridge/service_emulation_planner.py. It ranks only candidates with approved provenance/licence/terms/security evidence, operational verification, matching feature coverage, data classification, deployment mode, and known cost. Unknown-cost candidates fail closed; paid candidates require explicit allow_paid=true.
- Authenticated MCP tool plan_service_emulation in bridge/mcp_server.py. It returns a candidate recommendation only; it does not install, execute, or activate a service.
- Unit tests in bridge/test_service_emulation_governance.py and bridge/test_service_emulation_planner.py, plus MCP exposure/authentication tests in bridge/test_mcp_server.py.

The evaluator checks recorded provenance, third-party source and licence identification, clean-room evidence, restricted-material declarations, patent escalation state, service terms, and security review. It returns eligibility for human approval, not an automatic legal approval. Conditional approvals remain blocked until conditions are explicitly enforced. It does not search patent registers or determine infringement.

**Verification boundary:** files and MCP registration have been committed and re-fetched from staging. GitHub Actions execution is not yet verified; the repository's recent Actions failures were associated with account spending-limit blocks and unavailable job logs. Do not treat the tests as passed until a runner executes them. No production deployment or merge is authorized.

### Initial Koofr WebDAV adapter

A first bounded storage adapter is now present:
- `bridge/koofr_webdav_adapter.py` implements status, a read-only PROPFIND connection probe, bounded GET, and opt-in PUT against Koofr's documented fixed HTTPS endpoint.
- `bridge/mcp_server.py` exposes authenticated tools for status, probe, read, and write.
- `api/index.py` explicitly includes the new governance, planner, and Koofr modules in the Vercel cold-start overlay.
- `bridge/test_koofr_webdav_adapter.py` and MCP tests cover credentials redaction, path traversal rejection, read/write gates, redirect rejection, and authenticated tool routing.

Writes require both `FLYBRAIN_KOOFR_WEBDAV_ALLOW_WRITE=true` on the server and `confirm_write=true` on the individual call. Object size is capped at 1 MB. No delete, move, share, or synchronization operation is implemented. The adapter is not configured with credentials and has not yet completed a live Koofr connection or file round-trip.

**Deployment verification:** the latest Vercel Preview deployment loaded the new modules successfully and the live `/health` endpoint returned HTTP 200. Its response lists all four Koofr MCP tools and reports `configured=false`, `connection_verified=false`, and `write_enabled=false`. This confirms import and registration only; it does not prove Koofr connectivity or a storage round-trip. GitHub Actions unit tests have not yet been observed running for these commits.

Official connection instructions: https://app.koofr.net/help/webdav

**Remaining implementation boundary:** automated service discovery and candidate-source verification, a persistent registry, full USCL interface integration, multi-cloud replication, and restore verification remain unimplemented. The current planner accepts candidate evidence as input; it does not maintain or independently verify a catalogue. The planner validates finite cost estimates and uses supported-feature breadth only as a tie-breaker after all required gates pass. USCL remains design-only until a real backend adapter passes its acceptance tests. Existing capability-mesh routes do not constitute a general service factory or production-ready multi-cloud platform.
