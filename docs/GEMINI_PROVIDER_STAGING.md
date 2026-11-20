# Gemini Provider — Staging Integration Plan

**Status:** Design-only staging proposal. Provider disabled; no inference calls are made by this change.

## Objective

Introduce Google Gemini as a separately governed provider for FlyBrain/URCAL. Gemini is an additional analysis and review option; it does not replace Grok, ChatGPT, or existing providers.

## Proposed responsibility split

- **Grok:** repository exploration, implementation tasks, and independent code review.
- **ChatGPT:** integration design, provider governance, security/cost controls, and acceptance verification.
- **Gemini:** independent review of code and technical documents, multimodal inspection of explicitly approved non-sensitive material, and test-case/edge-case generation.

Assignments are advisory until an auditable task ledger and explicit agent execution channel are available. Do not claim agents are communicating directly unless a verified integration exists.

## Staging-only provider contract

Suggested configuration names:

- Provider ID: `google_gemini`
- Secret name: `gemini_api_key` (Supabase Vault only)
- Runtime environment binding: `GEMINI_API_KEY` (server-side only)
- Enable flag: `FLYBRAIN_GEMINI_ENABLED=false`
- Inference gate: `INFERENCE_ENABLED=false` remains authoritative.

The secret must never be committed, printed, returned by diagnostics, included in prompts, or exposed to browser/client code. Do not duplicate the key in GitHub Actions, Vercel, Cloudflare, or other services until the specific target's secret storage and access scope have been reviewed.

## Zero-cost admission policy

A free-tier account or a model appearing in a catalog is not proof that a particular request is free.

Before enabling any model:
1. Verify the exact model ID and current official Google pricing for the intended API and region.
2. Verify free-tier eligibility, quotas, rate limits, and applicable data-use terms.
3. Require explicit, fresh pricing/quota evidence from a trusted server-side source; reject caller-supplied claims.
4. Enforce a hard zero-cost policy. If price or quota evidence is missing, stale, ambiguous, or non-zero, fail closed.
5. Disable paid fallback, automatic billing, and any route that could silently switch to a paid model.
6. Keep inference disabled until a separate approval and controlled staging test.

No payment method, subscription, paid API tier, or financial commitment is permitted under this plan.

## Data protection

- Default to public, non-sensitive test inputs only.
- Never send repository secrets, API keys, credentials, private user data, private research, or confidential project material to Gemini.
- Treat model output as untrusted input. It cannot authorize tool execution, secret access, deployments, or policy changes.
- Apply input minimization, output validation, bounded token limits, request timeouts, and rate limits.
- Keep provider logs free of prompts and secret values unless a separately approved privacy design explicitly requires safe, redacted telemetry.

## Required implementation and acceptance gates

This document does not implement a transport adapter or activate Gemini. A later code PR must include:

- An isolated provider adapter with no network activity at import time.
- Explicit model allowlisting; no arbitrary model IDs from callers.
- Server-side secret retrieval only, with no secret value in logs or responses.
- Fail-closed zero-cost/quota admission backed by trusted evidence.
- Unit tests for disabled-by-default behavior, missing/invalid credentials, non-zero or unknown pricing, stale quota evidence, provider errors, and paid-fallback rejection.
- A mock-only test suite that can run without a Google key or network access.
- Documentation of current official pricing and data-use terms, checked at implementation time.
- No production deployment, main-branch merge, or inference enablement as part of the staging PR.

## Current activation state

| Control | Required value |
|---|---|
| `FLYBRAIN_GEMINI_ENABLED` | `false` |
| `INFERENCE_ENABLED` | `false` |
| Paid fallback | prohibited |
| Permitted test data | public/non-sensitive only |
| Deployment target | staging branch only |

## Human setup boundary

A project owner must complete Google account sign-in and create/authorize any API credential through Google's official interface. The key must be stored directly in the approved secret vault; it must not be pasted into chat or committed to the repository. If a free-tier key cannot be obtained without a payment method or paid commitment, stop and leave the provider disabled.
