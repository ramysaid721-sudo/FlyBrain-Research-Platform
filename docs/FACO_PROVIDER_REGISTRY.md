# FACO Provider Registry — Staging Prototype

Status: isolated prototype on `faco-provider-registry-prototype`; not connected to the live dispatcher.

## Purpose

Introduce a deterministic provider-selection boundary before adding additional compute providers. The selector is side-effect free: it does not create resources, access credentials, make network requests, or launch work.

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
6. Enable one additional provider only after its free allowance, data policy, network scope, and shutdown behavior are verified.

## Local tests

Run from the repository root:

```bash
python -m unittest worker.test_provider_registry -v
```

The test suite covers zero-cost admission, missing/stale quota evidence, circuit breaker, health, concurrency, strict input validation, runtime and data-class constraints, network/region requirements, and deterministic ordering.
