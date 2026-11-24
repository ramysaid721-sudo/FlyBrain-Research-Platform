# FACO Provider Registry — Staging Prototype

Status: isolated prototype on `faco-provider-registry-prototype`; not connected to the live dispatcher.

## Purpose

Introduce a deterministic provider-selection boundary before adding additional compute providers. The selector is side-effect free: it does not create resources, access credentials, make network requests, or launch work.

## External reasoning-model data boundary

FlyBrain's external reasoning-model policy is **public data only**. Before an external inference request is constructed, the caller must enforce `worker.model_data_policy.assert_external_model_input_allowed` with an exact `data_class="public"` classification and explicit false values for both `contains_secrets` and `contains_personal_data`.

The additional `worker.model_data_scanner.assert_external_model_payload_safe` helper applies that metadata check to the exact serialized payload and screens for common high-confidence secret formats, credential assignments, email addresses, and phone-like numbers. It returns rule identifiers only and never returns matched values. Unknown, internal, private, confidential, secret-bearing, personal-data-bearing, or unverified inputs fail closed.

**Important limitation:** content screening is heuristic defense-in-depth, not a complete secret/PII detector. It can miss novel, encoded, fragmented, or obfuscated sensitive content and can flag benign public examples. A clean scan does not prove that a payload is safe or public. The caller must still use trusted provenance/classification and must never send credentials, API keys, tokens, private source code, personal information, or operational secrets to an external model.

No model provider is activated by this policy change. The Staging Chat bridge now routes configured provider calls through the public-only policy and content scanner using the exact serialized HTTP request body immediately before network transfer; the request must include an explicit public-data attestation with both sensitive-data flags set to false. This attestation is supplied by the authenticated caller and is not independent cryptographic provenance. The scanner remains heuristic defense-in-depth, not proof that a payload is public or safe. Keep inference disabled until source provenance is independently established and the guard has passed deployment-level tests; no payload mutation is permitted after screening.

The dedicated policy and scanner tests are run with the provider-registry tests:

```bash
python -m unittest worker.test_provider_registry worker.test_model_data_policy worker.test_model_data_scanner -v
```

## Fail-closed admission rules

A provider offer is eligible only when all of the following are explicitly true:

- Provider is enabled and healthy; its circuit breaker is closed.
- Free capacity is confirmed by an account/quota check.
- Quota evidence must include an explicit age and be no older than the task's configured freshness window (default: 120 seconds). Missing or stale evidence is rejected.
- Estimated cost is explicitly supplied and must be exactly USD 0. A positive task budget never authorizes a paid provider in the current free-only FACO policy.
- A concurrency slot is available.
- Runtime, capability, data-class, network, region, and maximum-duration requirements are satisfied.

Unknown free capacity is not treated as free. A missing cost estimate cannot silently become zero because the offer requires an explicit cost field.

## Deterministic selection

Eligible offers are ordered by configured priority, then utilization ratio, then provider name. This makes selection reproducible and avoids random placement. Rejected offers include a machine-readable reason suitable for audit logs.

## Current provider facts

The live Staging deployment still uses one Vercel Sandbox worker adapter. GitHub-hosted Actions jobs have recently failed before their first step because no runner was allocated. Railway and Render have not been qualified as execution providers, and Cloudflare is not currently connected through an authorized tool in this environment. TinyFish remains excluded due to its negative wallet balance.

Therefore this prototype does not claim multi-cloud execution. It establishes the admission policy that must pass before any provider is enabled.

## Next integration gates

1. Add provider-specific quota/health probes with bounded timeouts.
2. Populate offers only from verified account state; never hard-code a provider as free.
3. Persist the selected provider and its quota evidence with the execution record.
4. Add transactional claim/dispatch integration with lease fencing and idempotency.
5. Test fallback after provider outage, capacity exhaustion, and stale quota data.
6. Wire the public-only metadata guard and content scanner into the final external inference request path before enabling any model.
7. Enable one additional provider only after its free allowance, data policy, network scope, and shutdown behavior are verified.

## Local tests

Run from the repository root:

```bash
python -m unittest worker.test_provider_registry worker.test_model_data_policy worker.test_model_data_scanner -v
```

The provider-registry suite covers zero-cost admission, missing/stale quota evidence, circuit breaker, health, concurrency, strict input validation, runtime and data-class constraints, network/region requirements, and deterministic ordering. The model-data-policy suite verifies public-only admission and rejection of sensitive or unverified classifications. The scanner suite covers representative secret formats and conservative PII patterns.
