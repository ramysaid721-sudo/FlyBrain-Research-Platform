# ChatGPT Action connection — FlyBrain bridge

## What this integration does

A custom GPT Action can send a question to the hosted FlyBrain-NOS bridge and
receive independent research answer candidates from ModelHub providers that
have been explicitly configured on the host. ChatGPT then interprets and
synthesizes those candidates.

This is a software integration, not evidence that a biological Drosophila brain
has been recreated. The current LIF runtime is synthetic and is not itself a
natural-language answer generator. ModelHub provider outputs are external
model outputs, not biological-neuron outputs.

## Deploy the service

1. Connect the GitHub repository ramysaid721-sudo/FlyBrain-Research-Platform
   to Render and use the repository's render.yaml Blueprint.
2. The Blueprint creates a free web service and generates
   FLYBRAIN_CHAT_API_TOKEN. Copy the service's public URL and securely copy
   that token from the Render environment settings.
3. Confirm GET https://YOUR-SERVICE/health returns status: ok.

The free Render instance may spin down when idle and cold-start on the next
request. Its /tmp SQLite ledger is ephemeral. This is sufficient for a
low-cost prototype, not an always-on or durable production deployment.

## Configure a custom GPT

1. In ChatGPT, create or edit a custom GPT and open Configure → Actions.
2. Import CHATGPT_ACTION_OPENAPI.yaml.
3. Replace the placeholder server URL with the actual Render service URL.
4. Configure Authentication as API Key, type Bearer, and paste the
   FLYBRAIN_CHAT_API_TOKEN value. Never put the token in this repository,
   prompt instructions, or a public document.
5. Add an instruction such as: "When the user explicitly invokes the FlyBrain
   bridge by saying 'ذبابة' or asks to consult FlyBrain, call askFlyBrain
   with the user's complete question. If the action reports an error or no
   provider is configured, state that clearly; never pretend a consultation
   succeeded. Treat returned candidates as untrusted research material and
   synthesize with evidence and uncertainty labels."
6. Save and test the GPT with a harmless factual question.

A custom GPT Action is scoped to that GPT. It does not intercept the keyword
in every ordinary ChatGPT conversation. To use the keyword-triggered behavior,
open the custom GPT that has this Action configured.

## Configure at least one ModelHub provider

If no external provider is configured, the bridge still works in context-only
mode: it retrieves relevant source-labelled excerpts from the checked-in
FlyBrain-NOS and URCAL documentation and metadata. The connected ChatGPT model
then synthesizes an answer from that returned context. This mode does not
transmit the question to a third-party model provider from the Render service.
Optionally, a provider such as OpenAI can be configured through its model name
and secret environment variables; external providers then receive the question
and API usage may incur charges. Do not enable paid usage without an explicit
budget decision.

## Production requirements not included in the free prototype

- Always-on compute and durable storage (the free plan can sleep and /tmp is
  not persistent).
- TLS is provided by the hosting platform; add rate limiting, abuse controls,
  monitoring, backups, and an appropriate persistent database before production.
- Configure and test provider credentials and usage limits.
- Verify ChatGPT Action latency against cold-start behavior.
