# FlyBrain ChatGPT bridge — source validation

Date: 2026-11-17
Source baseline: v0.14.0 archive plus repository overlay
Runtime: Python 3.13.5

## Implemented
- Authenticated WSGI endpoint: GET /health, POST /v1/ask.
- Bearer token must be at least 32 characters; request bodies and question length are bounded.
- The bridge delegates to the existing FlyBrain-NOS ModelHub consultation workflow and returns only successful provider candidates.
- No provider configured returns HTTP 503; all configured providers failing returns HTTP 502.
- OpenAPI contract for a custom GPT Action and Render Blueprint.
- Overlay script copies the bridge and tests into the extracted release and corrects runtime version exports.

## Fresh local verification
- URCAL: 68 passed.
- FlyBrain-NOS tests including bridge tests: 81 passed.
- Integrated FlyBrain-NOS + URCAL test runner: 81 passed.
- Total independent test runs: 149 passed.
- Python compileall: passed.
- TOML parsing and runtime version exports: passed (urcal 0.3.1, flybrain_os 0.13.3).

## Not yet deployed or connected
- Render service has not been deployed; the Render app connection is not yet confirmed.
- No ModelHub provider credentials are configured. Therefore the endpoint will correctly return HTTP 503 until one provider/model pair is configured.
- No ChatGPT custom GPT Action has been created or imported. The OpenAPI server URL is a placeholder until a deployed Render URL exists.
- The Render free tier may sleep while idle and its /tmp database is ephemeral. This is not a 24/7 durable production service.
- A custom GPT Action is only available inside that custom GPT; it cannot intercept the keyword in every normal ChatGPT conversation.
- No claim is made that the LIF runtime is a biologically validated Drosophila brain or a natural-language generation system.

## GitHub Actions
The latest run before this bridge change failed before any job steps were recorded. It did not provide runner logs or a definitive cause. The new commit will trigger another run; results must be inspected independently.
