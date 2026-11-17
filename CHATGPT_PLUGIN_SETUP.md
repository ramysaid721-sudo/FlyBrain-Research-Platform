# FlyBrain ChatGPT plugin and MCP connection

## What is ready
The repository contains a bearer-authenticated Streamable HTTP MCP endpoint at
\`/mcp\` with one read-only tool, \`ask_flybrain\`. It returns source-labelled
FlyBrain-NOS and URCAL excerpts; if ModelHub providers are configured, it can
also return their candidate answers. Without providers, ChatGPT itself can
synthesize the retrieved context. The synthetic LIF runtime is not a validated
biological Drosophila brain or a standalone language model.

## ChatGPT app route for a personal Free account
OpenAI's current Plugin Creator workflow is the supported starting point for
creating a reusable plugin. Install/connect Plugin Creator, then start a chat
with \`@plugin-creator\`. Ask it to create a plugin named **FlyBrain** with a
tool named \`ask_flybrain\` that sends the complete question to the FlyBrain MCP
server and returns the structured result. Use the remote endpoint
\`https://YOUR-RENDER-SERVICE.onrender.com/mcp\` and Bearer authentication
with the generated \`FLYBRAIN_CHAT_API_TOKEN\`. If Plugin Creator offers
ChatGPT Sites hosting for the app, use that supported hosted-app path for a
personal plan. Review the generated tool schema and test it before use.

Important: direct custom remote MCP server connections are currently limited
to Business and Enterprise/Edu; Pro supports read/fetch-only custom MCP apps.
ChatGPT Sites-hosted plugin apps are documented as available on any plan.
Plugin Creator must determine whether it can securely wrap this external
endpoint in a Sites-hosted plugin for this account. Do not paste the bearer
token into plugin instructions, a public document, or repository source; put it
only into the app's designated secret/authentication field.

## Suggested Plugin Creator request
Create a ChatGPT plugin called FlyBrain. It must expose one read-only research
tool, ask_flybrain(question), connected to the authenticated FlyBrain MCP
endpoint at https://YOUR-RENDER-SERVICE.onrender.com/mcp. Use Bearer
authentication stored as a secret, not in source code or instructions. When
the user says the exact keyword "ذبابة" or asks to consult FlyBrain, call
ask_flybrain with the user's complete question, then synthesize the returned
research context using the current ChatGPT model. Cite the returned source
paths in prose. Clearly distinguish documented evidence, model-generated
interpretation, and open hypotheses. Never claim the simulated LIF runtime is
a biologically validated fly brain. If the tool is unavailable, say so and do
not pretend it was called. Do not expose credentials or add write/delete tools.

## Deployment
Import this repository into Render as a Blueprint and use the root
\`render.yaml\`. It creates one Free web service in Frankfurt and generates
\`FLYBRAIN_CHAT_API_TOKEN\`. Verify \`GET /health\` and then test the MCP
endpoint. The free instance sleeps after 15 minutes idle, wakes on demand,
and has ephemeral local storage. It can keep working while the phone is off,
but it is not 24/7 always-on and its first request after sleep may take about
one minute. No paid ModelHub API key is required for context-only operation.

## Invocation and scope
After the plugin is created, invoke it in ChatGPT by selecting it or using its
\`@FlyBrain\` mention, then ask your question. Plugin tools are not a global
interceptor for every ordinary chat; the app must be active/selected in the
conversation. The keyword rule applies inside the plugin workflow.

## Credentials and privacy
The Render Blueprint generates the bearer token. Keep it in Render's secret
environment settings and the plugin's secret authentication field only.
Questions are processed by the Render service. In provider-free mode, the
service retrieves local source excerpts and returns them to ChatGPT; ChatGPT
then generates the natural-language answer. If you later configure external
ModelHub providers, question text and context will also be sent to those
providers and API charges may apply. Do not configure a paid provider without
an explicit budget decision.
