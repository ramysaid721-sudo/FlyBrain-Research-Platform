const INFERENCE_ENABLED = false; // Explicit code-level kill switch; do not enable before zero-spend verification.

const JSON_HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};

function reply(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function equalSecret(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function containsSensitivePattern(text: string): boolean {
  const patterns = [
    /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/,
    /\bAKIA[0-9A-Z]{16}\b/,
    /\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/,
    /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/,
    /\bsk_(?:live|test)_[A-Za-z0-9]{12,}\b/,
    /\bsk-[A-Za-z0-9_-]{20,}\b/,
    /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/,
    /(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*["']?[^\s"'\x60]{8,}/i,
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
  ];
  return patterns.some((pattern) => pattern.test(text));
}

async function readVaultSecret(name: string): Promise<string> {
  const base = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!base || !serviceKey) throw new Error("server_configuration_missing");
  const response = await fetch(`${base}/rest/v1/rpc/flybrain_openrouter_secret`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": serviceKey,
      "Authorization": `Bearer ${serviceKey}`,
    },
    body: JSON.stringify({ p_name: name }),
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error("vault_lookup_failed");
  const value = await response.json();
  if (typeof value !== "string" || !value) throw new Error("vault_secret_missing");
  return value;
}

Deno.serve(async (req: Request) => {
  if (req.method === "GET") {
    return reply({
      service: "flybrain-openrouter-staging",
      status: "ok",
      model_route: "openrouter/free",
      inference_enabled: INFERENCE_ENABLED,
      deployment_mode: "staging",
    });
  }

  if (req.method !== "POST") return reply({ error: "method_not_allowed" }, 405);

  // Default-deny: no secret lookup and no external transfer unless explicitly enabled.
  if (!INFERENCE_ENABLED) {
    return reply({
      error: "inference_disabled",
      external_data_transfer: false,
      reason: "staging_feature_flag_is_not_enabled",
    }, 503);
  }

  const suppliedToken = req.headers.get("x-flybrain-openrouter-token") ?? "";
  let expectedToken = "";
  try {
    expectedToken = await readVaultSecret("flybrain_openrouter_bridge_token");
  } catch {
    return reply({ error: "server_configuration_unavailable", external_data_transfer: false }, 503);
  }
  if (!equalSecret(suppliedToken, expectedToken)) {
    return reply({ error: "unauthorized", external_data_transfer: false }, 401);
  }

  const contentLength = Number(req.headers.get("content-length") ?? "0");
  if (!Number.isFinite(contentLength) || contentLength < 1 || contentLength > 24000) {
    return reply({ error: "invalid_request_size", external_data_transfer: false }, 413);
  }

  let payload: Record<string, unknown>;
  try {
    payload = await req.json();
  } catch {
    return reply({ error: "invalid_json", external_data_transfer: false }, 400);
  }
  if (
    payload.scope !== "public_project_research" ||
    payload.data_classification !== "public" ||
    typeof payload.question !== "string" ||
    !payload.question.trim() ||
    payload.question.length > 4000 ||
    typeof payload.context !== "string" ||
    payload.context.length > 16000
  ) {
    return reply({ error: "public_research_payload_required", external_data_transfer: false }, 422);
  }

  const serialized = JSON.stringify(payload);
  if (new TextEncoder().encode(serialized).length > 24000 || containsSensitivePattern(serialized)) {
    return reply({ error: "external_data_policy_blocked", external_data_transfer: false }, 422);
  }

  let apiKey = "";
  try {
    apiKey = await readVaultSecret("openrouter_api_key");
  } catch {
    return reply({ error: "provider_configuration_unavailable", external_data_transfer: false }, 503);
  }

  let upstream: Response;
  try {
    upstream = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://flybrain-research-platform.vercel.app",
        "X-Title": "FlyBrain Research Platform",
      },
      body: JSON.stringify({
        model: "openrouter/free",
        messages: [
          { role: "system", content: "Answer using only the supplied public project context. Do not request or infer private information. If context is insufficient, say so." },
          { role: "user", content: payload.question + "\n\nPublic project context:\n" + payload.context },
        ],
        max_tokens: 512,
        temperature: 0.2,
        stream: false,
        usage: { include: true },
      }),
      signal: AbortSignal.timeout(35000),
      redirect: "error",
    });
  } catch {
    return reply({ error: "upstream_unavailable", external_data_transfer: false }, 502);
  }

  if (!upstream.ok) {
    // Do not relay provider response bodies or headers; they may contain diagnostics.
    return reply({ error: "upstream_request_failed", external_data_transfer: true }, 502);
  }

  let result: Record<string, unknown>;
  try {
    result = await upstream.json();
  } catch {
    return reply({ error: "invalid_upstream_response", external_data_transfer: true }, 502);
  }
  const choices = Array.isArray(result.choices) ? result.choices : [];
  const first = choices[0] as Record<string, unknown> | undefined;
  const message = first && typeof first.message === "object" && first.message !== null
    ? first.message as Record<string, unknown> : {};
  const usage = typeof result.usage === "object" && result.usage !== null
    ? result.usage as Record<string, unknown> : {};
  const model = typeof result.model === "string" ? result.model : "";
  const answer = typeof message.content === "string" ? message.content : "";
  if (!model.endsWith(":free") || !answer.trim() || usage.cost !== 0) {
    return reply({
      error: "free_route_or_zero_cost_not_verified",
      external_data_transfer: true,
    }, 502);
  }

  return reply({
    status: "completed",
    provider: "openrouter",
    requested_model_route: "openrouter/free",
    served_model: model,
    answer,
    usage: { cost: 0 },
    external_data_transfer: true,
    data_scope: "public_project_research",
  });
});
