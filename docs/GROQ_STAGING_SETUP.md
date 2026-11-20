# Groq Staging Admission — Zero-Cost Gate

## Status

This change adds a pure, fail-closed admission policy only. It does not add a
Groq transport, make inference requests, enable ModelHub, or change any
deployment. Inference remains disabled.

## Admission requirements

A future Groq transport must reject a request unless all of the following
conditions are satisfied:

1. The exact model identifier is explicitly allowlisted.
2. Provider-derived pricing evidence identifies that exact model.
3. Input and output prices are both explicitly numeric zero. Missing prices
   are rejected.
4. Provider-derived free-quota evidence is fresh (no older than 120 seconds)
   and reports positive remaining request and token quota.
5. The evidence source is HTTPS and the free quota is explicitly confirmed.

The policy rejects stale, malformed, mismatched, incomplete, positive-cost,
or unknown evidence. It fails closed.

## Current operational limitation

The Groq model-catalog response observed during the initial staging check
returned HTTP 200, but the listed model pricing fields were positive for the
models inspected. A successful API-key authentication and the existence of
a free account tier do not establish a zero-dollar hard spending ceiling.
Rate-limit headers also do not prove that a request cannot become billable.

Therefore this repository change intentionally does not send inference
requests. Before a transport can be enabled, the operator must identify a
provider-supported, machine-verifiable source proving zero effective price
and remaining free quota for the exact model. If Groq cannot provide that
evidence on the current account tier, the correct behavior is to keep Groq
disabled and use local/offline execution or context-only mode.

## Security boundaries

- No API key is read by this module.
- No secrets are embedded in source or tests.
- No private or personal data is accepted by this policy module.
- No paid fallback is implemented.
- No production configuration is changed.
