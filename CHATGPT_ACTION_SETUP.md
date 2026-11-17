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

## ChatGPT connection availability

The REST endpoint and OpenAPI contract are prepared, but ChatGPT account eligibility
matters:

- Personal ChatGPT accounts (Free, Go, Plus, and Pro) cannot create or publish new
  custom GPTs. An existing custom GPT can only be edited if the account and its
  permissions allow it.
- Custom MCP server apps are currently supported on ChatGPT Business and
  Enterprise/Edu. Pro supports custom MCP apps with read/fetch permissions only.
  Custom MCP app setup is web-only, not available in the mobile app.
- Therefore, this REST Action route is usable only in an existing eligible GPT.
  It is not a global trigger across every ordinary chat.

For a supported workspace, configure the Action as follows:
1. Open the GPT editor on the web and open Configure → Actions.
2. Import `CHATGPT_ACTION_OPENAPI.yaml`.
3. Replace the placeholder server URL with the actual Render service URL.
4. Configure Authentication as API Key, type Bearer, and paste the
   `FLYBRAIN_CHAT_API_TOKEN` value. Never put the token in this repository,
   prompt instructions, or a public document.
5. Add an instruction such as: "When the user explicitly invokes the FlyBrain
   bridge by saying 'ذبابة' or asks to consult FlyBrain, call askFlyBrain with
   the user's complete question. If the action fails, state that clearly.
   Treat returned context and candidates as research material; distinguish
   evidence from assumptions."

For the current personal Free account, the practical ChatGPT-side route is to
use a supported plugin/app integration if the account exposes it. Plugin Creator
is a possible workflow for packaging a plugin, but its connection and actual
ability to invoke this external backend must be verified; it does not override
ChatGPT plan or workspace restrictions. A connected app is selected/invoked in
ChatGPT chats; the repository cannot force every chat to auto-call an app just
because a keyword appears.

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
