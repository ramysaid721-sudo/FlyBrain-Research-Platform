# Unified Storage Compatibility Layer (USCL)

**Status:** architecture proposal for the FlyBrain staging branch; no provider is claimed connected or operational by this document.
**Target:** FlyBrain / URCAL.
**Objective:** expose a stable, provider-neutral storage interface and emulate common storage capabilities over storage accounts and infrastructure the user is already authorized to access. Prefer mature open-source software and existing protocols over reimplementing storage systems.

## 1. Governing principle: emulate interfaces, not entitlements

FlyBrain may provide a familiar API over a backend only when that backend and account legitimately support the required operations. The compatibility layer must not bypass quotas, payment controls, authentication, rate limits, or provider terms. It must not disguise usage or create the illusion of unlimited capacity.

A façade can normalize an interface; it cannot manufacture capacity, durability, or an SLA. The backend's actual quota, retention, throughput, and API limits remain authoritative.

## 2. Canonical storage interface

Define a narrow StorageBackend contract:

- health_check(): non-mutating reachability and authentication check.
- stat(path): metadata for one object.
- list(prefix, cursor, limit): paginated listing.
- read(path, byte_range): bounded object read.
- write(path, stream, metadata, if_match): authorized write with optimistic concurrency.
- delete(path, if_match): explicit deletion only.
- copy(source, destination): server-side copy when supported, otherwise bounded stream copy.
- create_share(path, expiry, permission): only where safe expiring links are supported.
- usage(): quota and usage if exposed; unknown must remain unknown.
- capabilities(): explicit feature matrix, never inferred from provider name alone.

Canonical metadata should include backend ID, object key, size, content type, modified time, checksum when available, ETag/version, and provenance.

## 3. Adapter strategy: reuse existing protocols

Priority order:

1. WebDAV adapter for providers that expose WebDAV, such as a configured Koofr endpoint or self-hosted Nextcloud.
2. S3-compatible adapter for MinIO, Garage, SeaweedFS S3 gateway, or an existing S3-compatible account.
3. Provider-native adapters only where required, such as Dropbox API or Supabase Storage, using authorized OAuth/API credentials.
4. Local filesystem adapter for development, tests, temporary staging, and user-controlled persistent disks.
5. Optional rclone integration as a transport/synchronization bridge where it reduces custom code; use documented commands and supported backends.

Do not assume support for WebDAV, S3, server-side copy, versioning, checksums, or expiring shares until a live capability probe confirms it.

## 4. Services emulated on top of storage

The façade may expose logical services over one or more backends:

- Object store: bucket/prefix abstraction, metadata, multipart upload where supported, bounded downloads.
- File service: directory-like paths, move/copy, metadata, share links where supported.
- Sync service: incremental manifests, checksums, conflict detection, resumable transfers, explicit conflict policies.
- Backup service: content-addressed snapshots, manifests, retention policy, restore verification.
- Artifact registry: immutable artifact IDs, SHA-256 verification, provenance records, references to stored objects.
- Search index: metadata and extracted-text index separate from original files; re-indexing must be possible.
- Version history: native versioning when available; otherwise append-only version objects and manifests, with extra storage cost reported.
- Temporary workspace: short-lived scratch space only; Vercel serverless temporary files are not durable storage.

These are compatibility services, not a promise to reproduce every feature or SLA of a commercial platform.

## 5. Reusable building blocks

Prefer mature software with active maintenance and clear licenses:

- Nextcloud: file sync/share and WebDAV when a persistent host is available.
- MinIO, Garage, or SeaweedFS: self-hosted S3-compatible object storage when persistent compute and disk are available.
- rclone: connect and synchronize supported remotes without writing a bespoke transfer engine.
- restic or Kopia: encrypted, deduplicated backup and snapshot workflows.
- SQLite: local metadata/catalog for single-instance staging; migrate to a shared database before multi-instance production.
- FastAPI/Starlette or the existing FlyBrain bridge: thin authenticated API façade; do not duplicate the storage engine.

Review license, maintenance, security posture, and hosting requirements before selecting a component.

## 6. Candidate backend inventory

Dropbox, Koofr, and the two existing Supabase projects have been mentioned in project context. They are candidates, not verified storage mounts or confirmed available capacity.

- Dropbox: use authorized connector/API operations if the connector exposes the required actions; do not infer access from a connected badge.
- Koofr: test its documented WebDAV endpoint with a scoped app password; never put credentials in chat or source control.
- Supabase Storage: inspect existing project storage configuration and quota before writing; do not create a third project or upgrade a plan for this design.
- Vercel: use for stateless API façade and metadata endpoints only; its function filesystem is ephemeral, not durable object storage.
- Any future host: qualify persistent-disk semantics, egress limits, sleeping behavior, backups, and free-tier terms before use.

## 7. Security and integrity

- Store secrets only in the platform secret manager; never commit, log, or return them.
- Use least-privilege, revocable credentials per backend and operation.
- Classify data before transfer. Confidential and restricted data stays local or on an explicitly approved backend.
- Encrypt sensitive artifacts client-side before upload when appropriate; keep keys separate from the storage provider.
- Verify SHA-256 after upload and restore where possible.
- Use atomic manifests and optimistic concurrency to prevent silent overwrites.
- Make destructive deletion a separate explicit operation with retention/restore checks.
- Treat public share links as disclosure events; default to private.
- Prevent SSRF, path traversal, archive bombs, unbounded downloads, and cross-tenant object access.
- Keep an audit trail of actor, operation, backend, object identifier, result, and timestamp without recording file contents or credentials.

## 8. Cost and quota governor

Default policy: zero_cost_first.

- No paid provider, paid overage, or billable API call without explicit authorization.
- Enforce per-task byte, request, time, and concurrency ceilings.
- Read quota before writes where supported.
- Reserve headroom for restore and metadata operations.
- Stop rather than silently spill to a paid backend.
- Cache immutable public artifacts and deduplicate by checksum where policy permits.
- Represent cost as known_zero, known_nonzero, or unknown; unknown is not zero.
- Return a clear no-capacity/no-eligible-backend result instead of retrying indefinitely.

Free-tier use must comply with provider terms and documented quotas. No account cycling, quota evasion, credential sharing, or abuse of trial/free allocations.

## 9. Deployment phases

A. Inventory: verify available connectors and credentials, and list backend capabilities/quotas without reading secret values.
B. Contract and local tests: implement the canonical interface and filesystem fake; test path safety, pagination, checksums, concurrency, and fail-closed behavior.
C. First real backend: select one already-authorized backend with a documented protocol; run a tiny test object, verify read-back checksum, then delete it.
D. Compatibility façade: expose a small authenticated API and map only operations supported by the selected backend.
E. Resilience: add a second backend, sync manifests, restore drills, and explicit failover rules.
F. Production qualification: security review, independent tests, quota alerts, backup/restore evidence, and explicit approval before production deployment.

## 10. Acceptance criteria

The layer is not operational until:

1. At least one real backend passes authenticated health, write, read-back, checksum, list, and delete tests.
2. Unauthorized and cross-backend requests fail closed.
3. Unknown/insufficient quota and paid fallback cases stop safely.
4. Large transfers are bounded and resumable or explicitly unsupported.
5. Concurrent writes detect conflicts rather than silently overwrite.
6. Restore reproduces the original checksum.
7. Secrets do not appear in logs, API responses, or repository history.
8. Provider capability claims match observed tests.
9. No paid usage occurs without explicit authorization.
10. Production remains untouched until separately approved.

**Current implementation status:** design only. No storage adapter, persistent volume, S3 gateway, WebDAV mount, or storage API is asserted to be deployed by this document.
