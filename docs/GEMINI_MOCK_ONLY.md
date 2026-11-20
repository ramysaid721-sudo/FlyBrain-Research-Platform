# Gemini mock-only staging adapter

**Status:** Implemented as an isolated, deterministic test double. This is not a Gemini API integration.

## Safety properties

- No HTTP, SDK, socket, subprocess, or other network transport is imported or invoked.
- No environment variables, Supabase Vault RPC, or credential values are read.
- No Google API key is accepted by the adapter.
- The mock is disabled by default and must be enabled explicitly by a local test.
- Responses carry `mock=true`, `network_used=false`, and `credential_used=false`.
- Input is bounded to 4,000 characters and must be a non-empty string.
- Output is synthetic and must never be represented as a Gemini model result.

## Run the offline tests

From the repository root:

```bash
python -m unittest discover -s tests -p 'test_gemini_mock.py' -v
```

The test suite requires only the Python standard library. It does not require a Google key, network access, billing, or a Supabase connection.

## Explicit non-goals

This change does not implement a Google transport, model selection, quota verification, zero-cost admission, Vault secret retrieval, deployment, or inference. It does not change `INFERENCE_ENABLED` or `FLYBRAIN_GEMINI_ENABLED`. Live Gemini requests remain prohibited until a separate security and cost-admission review is approved.

## Staging boundary

Keep this work on `gemini-mock-only-staging`. Do not merge to `main`, deploy to Production, or connect this mock to a live provider route as part of this change.
