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


## Public pricing and quota verification — 2026-11-20

The official Gemini Developer API pricing page was reviewed on 2026-11-20:

- The Free tier is limited to selected models; free eligibility must be checked for the exact model and API feature, not inferred from the existence of an API key.
- Where the official pricing table marks standard input and output as free for a model, that does not make every tool or feature free. Grounding, caching, batch, priority, computer-use, and other capabilities have separate availability and/or pricing conditions.
- Google states that content submitted under the Free tier may be used to improve its products. Only public, non-sensitive test content is therefore permitted by this staging plan.
- The account-specific rate limits and remaining quota must be read from the owner's AI Studio project usage/limits view. A chart for Antigravity or another agent product is not evidence of Gemini Developer API quota.
- Paid-tier activation requires Cloud Billing setup and a payment method. This project explicitly prohibits that path.

Official references:
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://aistudio.google.com/docs/get-started

### Current admission decision

**DENY / NOT READY.** The Vault secret exists, but this repository review has not established the account-specific Gemini model quota, the exact model's free-tier availability for this project, or a trusted machine-readable zero-cost admission signal. Do not send a live API request, do not enable either provider flag, and do not configure paid billing. The Antigravity limits screenshot must not be reused as Gemini quota evidence.

This decision is intentionally fail-closed. A future implementation may proceed with mock-only adapter tests while inference remains disabled; live staging admission requires a separate review of the exact model, project quota, billing state, and data-use constraints.
