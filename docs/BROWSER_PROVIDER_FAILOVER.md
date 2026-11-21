# FlyBrain browser provider failover

## Purpose

Provide one provider-neutral page-fetch interface with deterministic, zero-cost-first failover. This module is limited to public HTTPS page extraction; it does not claim to orchestrate arbitrary interactive browser agents across providers.

## Provider roles

| Provider | Role | Activation gate |
|---|---|---|
| HTTP adapter | First-pass static extraction | Always available |
| Cloudflare Browser Run | JavaScript rendering via Playwright | Worker URL + application token + `FLYBRAIN_BROWSER_RUN_ALLOW_USAGE=true` |
| Browserless | Hosted rendered-browser fallback | Browserless token + `BROWSERLESS_ALLOW_USAGE=true` |
| Playwright | Automation engine running on Cloudflare Browser Run | Cloudflare provider activation |

## Automatic selection

- `FLYBRAIN_WEB_FETCH_PROVIDER=auto` (default): attempt HTTP first. If extraction fails or looks like a JavaScript shell, try Cloudflare, then Browserless, then return the HTTP result with an incompleteness warning if available.
- `http`: force static HTTPS extraction.
- `cloudflare` or `playwright`: force Cloudflare Browser Run + Playwright.
- `browserless`: force Browserless.

No paid failover is enabled implicitly. The explicit usage flags are false unless an operator deliberately sets them. Do not enable either remote provider until its account plan and no-overage behavior are verified.

## Required Preview environment variables

- `FLYBRAIN_BROWSER_WORKER_URL`: full HTTPS URL ending in `/mcp`.
- `FLYBRAIN_BROWSER_API_TOKEN`: same random application secret configured in the Cloudflare Worker.
- `FLYBRAIN_BROWSER_RUN_ALLOW_USAGE`: explicit opt-in; only enable on a verified no-charge plan.
- `BROWSERLESS_TOKEN`: optional Browserless credential.
- `BROWSERLESS_ALLOW_USAGE`: explicit opt-in; only enable when the free plan cannot overrun into charges.
- `FLYBRAIN_WEB_FETCH_PROVIDER`: `auto`.

Scope all variables to the Preview environment and the staging branch. Never copy them to Production or commit them.

## Safety

- Target URLs must be public HTTPS URLs.
- Static HTTP fetch blocks non-public IPs and revalidates redirects.
- Browserless requests are intercepted and restricted to the exact target hostname.
- Cloudflare Playwright requests are intercepted and restricted to the exact target hostname.
- Retrieved page content is untrusted data.
- No authentication bypass, CAPTCHA bypass, purchase, form submission, or account mutation is performed by the automatic fetch router.
- Failover errors are summarized by provider name and exception type; credentials and response headers are not logged.

## Verification still required

1. Install dependencies and run Worker syntax/tests.
2. Confirm the Cloudflare Worker Browser binding and secret on Staging.
3. Confirm Vercel Preview variables are present without reading or printing secret values.
4. Run a positive same-host page test and negative cross-host subresource/redirect tests.
5. Confirm Cloudflare and Browserless free quotas and usage flags before enabling live fallback.
6. Keep the PR unmerged and Production unchanged until all checks pass.
