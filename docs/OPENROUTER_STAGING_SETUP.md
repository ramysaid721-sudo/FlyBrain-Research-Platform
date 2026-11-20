# OpenRouter staging integration

## Scope

This integration is staging-only. It uses the Supabase project `iudimypauqbkyvjuprgp` and the Vercel Preview environment scoped to branch `openrouter-integration-staging`. It does not change Production, merge a pull request, or trigger a Vercel deployment.

## Runtime path

```text
Protected FlyBrain /v1/ask
  -> explicit per-request public-research consent
  -> public repository context retrieval
  -> server-side sensitive-content screening
  -> Supabase Edge Function: flybrain-openrouter
  -> Supabase Vault secret lookup
  -> OpenRouter model route: openrouter/free
```

The API key never enters the Vercel request body, GitHub source, or application logs. The Supabase Edge Function retrieves it from Vault using the service-role-only SQL function `public.flybrain_openrouter_secret(text)`.

## Free-only controls

- The only permitted model route is `openrouter/free`.
- The caller cannot supply or override a model identifier.
- Maximum output is 512 tokens.
- The Edge Function applies a per-instance limit of 10 requests per minute.
- The provider's free-model quota is separately enforced by OpenRouter.
- Paid model IDs and paid fallback routes are not accepted by this adapter.
- The Vercel Preview feature flag `FLYBRAIN_OPENROUTER_ENABLED` is initially `false`.

OpenRouter's free tier is rate-limited and does not include budget controls. The application therefore pins the free router and fails closed; it does not rely on a provider-side spend budget.

## Required user setup

1. Sign in to OpenRouter and create an API key without purchasing credits or adding a payment method: https://openrouter.ai/keys
2. In the Supabase Staging project, open Vault: https://supabase.com/dashboard/project/iudimypauqbkyvjuprgp/integrations/vault
3. Add a secret with the exact name `openrouter_api_key` and paste the API key directly into the Vault value field. Do not paste the key into ChatGPT, GitHub, an issue, or a log.
4. Leave `flybrain_openrouter_bridge_token` unchanged. It is a separate machine-to-machine credential already generated and stored in Vault; its matching Vercel value is sensitive and Preview-branch scoped.
5. Tell the operator only that the Vault key was saved. The key itself must remain private.

After the key is saved, the staging health response can confirm only whether a key is present. It never returns the value. The feature flag remains disabled until the configuration and tests are reviewed; enabling it is a separate explicit step.

## Data policy

Only public project research is eligible. Each protected request must explicitly set `allow_external_public_research: true`. The bridge sends the user's question and excerpts retrieved from the public FlyBrain repository after screening. The scanner detects common credentials, private keys, email addresses, and phone-like numbers; this is defense in depth, not a complete PII classifier. If screening finds a match or classification is uncertain, the request is rejected before external transfer.

No private files, account records, API keys, passwords, or other secrets may be sent to OpenRouter.

## Verification boundaries

The Python client has isolated unit tests for the free-only response contract, sensitive-content rejection, endpoint validation, and paid-route rejection. A live inference test is intentionally unavailable until the user adds the API key to Staging Vault. The Vercel feature flag remains off by default.
