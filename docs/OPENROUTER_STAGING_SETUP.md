# OpenRouter staging integration

## Scope

This integration is staging-only. It uses the Supabase project `iudimypauqbkyvjuprgp` and the Vercel Preview environment scoped to branch `openrouter-integration-staging`. Git pushes to this branch may automatically create Vercel Preview deployments; they do not deploy to Production. No paid plan, resource, or subscription is authorized.

## Runtime path

The intended path, once inference is explicitly enabled, is:

```text
Protected FlyBrain /v1/ask
  -> explicit per-request public-research consent
  -> public repository context retrieval
  -> server-side sensitive-content screening
  -> Supabase Edge Function: flybrain-openrouter
  -> Supabase Vault secret lookup
  -> OpenRouter model route: openrouter/free
```

The API key must never enter the Vercel request body, GitHub source, or application logs. The Supabase Edge Function retrieves it from Vault using the service-role-only SQL function `public.flybrain_openrouter_secret(text)`.

## Current deployment state

- The deployed Supabase Edge Function is deliberately hard-disabled for inference.
- Its GET health response reports whether the Vault key exists, but never returns the value.
- Every POST request returns HTTP 503 with `external_data_transfer: false`; no OpenRouter request is made.
- The Edge Function source is tracked at `supabase/functions/flybrain-openrouter/index.ts`.
- `FLYBRAIN_OPENROUTER_ENABLED` remains false in the Vercel Preview environment.
- The latest Staging commit has a READY Vercel Preview deployment. No Production deployment has been performed.

## Free-only controls in the client implementation

- The only permitted model route is `openrouter/free`.
- The returned model identifier must end in `:free`; any other served model is rejected.
- The upstream response must explicitly report `usage.cost = 0`; missing, invalid, or positive cost is rejected.
- The caller cannot supply or override a model identifier or paid fallback list.
- Maximum output is 512 tokens.
- The client refuses a non-zero or unreported cost after receiving the response.
- The provider's free-model quota is separately enforced by OpenRouter.

OpenRouter's Free plan does not include provider-side budget controls. The Free Models Router itself is documented as free and, on its own, falls back only to other free models; paid fallbacks must not be added. Therefore the current design relies on a fixed free-only route and application-side checks, not an account-level spend cap. This is not equivalent to a provider-side hard spending limit. The live path remains disabled until this residual limitation is explicitly accepted and the staging tests are verified.

## Required user setup

1. Sign in to OpenRouter and create an API key without purchasing credits or adding a payment method: https://openrouter.ai/keys
2. In the Supabase Staging project, open Vault: https://supabase.com/dashboard/project/iudimypauqbkyvjuprgp/integrations/vault
3. Add a secret with the exact name `openrouter_api_key` and paste the API key directly into the Vault value field. Do not paste the key into ChatGPT, GitHub, an issue, or a log.
4. Leave `flybrain_openrouter_bridge_token` unchanged. It is a separate machine-to-machine credential stored in Vault; its matching Vercel value is sensitive and Preview-branch scoped.
5. Tell the operator only that the Vault key was saved. The key itself must remain private.

The staging health response can confirm only whether a key is present. It never returns the value.

## Data policy

Only public project research is eligible. Each protected request must explicitly set both `question_is_public: true` (the authenticated operator's classification of the question) and `allow_external_public_research: true` (consent to transfer it). The server independently requires at least one excerpt from the pinned public release allowlist and rejects any source outside that allowlist. The bridge sends the question and those excerpts only after screening. The scanner detects common credentials, private keys, email addresses, and phone-like numbers; this is defense in depth, not a complete PII classifier. If trusted public context is absent or screening finds a match, the request is rejected before external transfer. Do not attest private, confidential, or personal material as public.

No private files, account records, API keys, passwords, or other secrets may be sent to OpenRouter.

## Verification boundaries

- `scripts/apply_chat_bridge.py` copies both the OpenRouter client and its tests into the FlyBrain release overlay.
- Seven OpenRouter client unit tests passed in a local isolated Python test harness.
- Ten Chat API unit tests passed in a local isolated Python test harness with the ModelHub provider module stubbed; these validate request gating and payload-screening behavior, not a full provider integration.
- GitHub Actions was triggered and retried, but its jobs failed before allocating a runner (`runner_id = 0`, no steps); the hosted CI suite is therefore not verified.
- The latest Staging commit has a READY Vercel Preview build, but this is not a live OpenRouter inference test.
- No live inference request has been sent. The Edge Function POST path remains hard-disabled.
