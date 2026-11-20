# FlyBrain Storage Encryption and Key Rotation — Staging Specification

Status: implementation specification; not a claim that encryption is deployed.

## Security objectives

- Encrypt persistent artifacts before they leave the worker process when application-layer confidentiality is required.
- Use authenticated encryption (AEAD), with AES-256-GCM or an equivalently reviewed AEAD construction.
- Use envelope encryption: a random data-encryption key (DEK) per object or bounded object group, wrapped by a key-encryption key (KEK) held only by an approved KMS/secret manager.
- Never store plaintext keys, KEKs, credentials, or unwrapped DEKs in Git, task records, logs, model prompts, or object metadata.
- Keep the existing public-data-only rule for external model calls. Encryption is not permission to transmit private data.

## Object format

Each encrypted object must carry only non-secret format metadata:
- format/version identifier;
- algorithm identifier;
- key identifier and key version;
- unique nonce/IV;
- wrapped DEK;
- authenticated ciphertext and authentication tag;
- non-sensitive content type and creation timestamp where required.

Bind object identity, tenant/project scope, schema version, and format version as AEAD associated data (AAD). Reject mismatches and authentication failures. Never reuse a nonce with the same AES-GCM key.

## Key hierarchy and rotation

1. Generate each DEK with a cryptographically secure random generator.
2. Encrypt the object with the DEK using AEAD.
3. Wrap the DEK with a KEK in the platform KMS/secret manager.
4. For routine KEK rotation, create a new KEK version and re-wrap DEKs; avoid re-encrypting large objects when cryptographic policy permits.
5. For DEK rotation or suspected compromise, decrypt and re-encrypt each object with a fresh DEK and nonce, then verify the new ciphertext before retiring the old wrapped key.
6. Maintain a bounded overlap window for old key versions so existing objects and backups remain recoverable. Retire old versions only after inventory, restore tests, and retention obligations are satisfied.
7. Record key-version changes and rotation outcomes without logging key material or plaintext.

Rotation must be scheduled and policy-driven (for example, periodic KEK rotation plus event-driven rotation on compromise). Do not randomly change keys on every read/write; that creates availability and recovery risks without improving the cryptographic guarantees.

## Storage and execution boundaries

- Require TLS for all network transfers; reject plaintext endpoints.
- Encrypt application artifacts before upload where feasible. Verify the underlying database/object-store encryption settings separately; provider-managed at-rest encryption is a distinct defense layer.
- Keep plaintext only in process memory or a restricted ephemeral workspace for the shortest practical period. Do not claim that storage encryption hides plaintext from a worker while it is actively processing it.
- Do not persist prompts or full model outputs by default. Retain the minimum task metadata, integrity hashes, and artifacts required for reproducibility.
- Apply short TTLs to temporary objects and clean them after verified completion or expiry. Keep required audit records; do not erase provider logs or backups.
- Backups and replicas must have equivalent encryption, key-access controls, retention limits, and tested restore procedures.

## Key custody and access control

- KEKs must be non-exportable where the KMS supports it.
- Separate encryption/decryption permissions from ordinary worker permissions; grant least privilege and scope access to the specific environment and purpose.
- Never place key material in environment files committed to source control, CI logs, issue comments, task payloads, or external-model requests.
- If no verified KMS/secret manager and zero-cost key custody are available, fail closed: do not claim application-layer encryption is active and do not invent a local key-management substitute.
- Key loss must be treated as data loss. Recovery material and recovery roles must be designed and tested before enabling encryption for persistent production data.

## Verification gates

Before enabling this in any environment:
1. Inventory every persistent store, cache, artifact bucket, database table, backup, and log destination.
2. Confirm provider-level encryption and transport settings from authoritative configuration, not assumptions.
3. Implement an audited AEAD storage adapter with KMS-backed envelope encryption.
4. Test tamper detection, wrong-key rejection, AAD mismatch, nonce uniqueness, interrupted writes, concurrent reads, key rotation, rollback, and backup restore.
5. Prove that logs, traces, exceptions, and model payloads contain neither plaintext secrets nor key material.
6. Verify TTL cleanup and ensure it does not remove audit evidence or required recovery material.
7. Run the tests in Staging and review the diff before any production rollout.

## External security-model review

A security model or agent may review only this public specification and synthetic test fixtures. It must be reached through a documented, authorized endpoint with verified identity, explicit zero-cost capacity, and reviewed retention/training terms. Its output is untrusted advice and must be independently checked. Do not try to suppress findings, manipulate the reviewer into approving the design, or send secrets/private source code/personal data.

## Current status and limitations

- A KMS-agnostic AES-256-GCM envelope-encryption adapter and synthetic unit tests now exist in `worker/storage_encryption.py` and `worker/test_storage_encryption.py` on the Staging prototype branch.
- The adapter exposes a `KeyWrapper` protocol only. No real KMS/secret-manager implementation, key custody, persistent-storage integration, scheduled rotation job, or storage migration is configured.
- The CI workflow now includes the new tests, but passing CI has not yet been independently verified.
- No external security-review agent endpoint has been verified or contacted. Railway currently has no projects and its agent connector tunnels are unavailable; Vercel billing-charge visibility returned `costs_not_found`, and its named Staging sandbox is stopped. No paid or uncertain-cost compute has been started.
- Existing provider-managed encryption, if any, does not prove application-layer encryption or FlyBrain-controlled key rotation.
- The current project policy remains public data only for external models; no private data is eligible.
