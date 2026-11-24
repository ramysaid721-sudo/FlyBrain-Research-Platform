import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};

function reply(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: HEADERS });
}

function equalSecret(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function rpc(name: string, args: Record<string, unknown>) {
  const base = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!base || !key) throw new Error("ledger_configuration_missing");
  const response = await fetch(`${base}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: key, Authorization: `Bearer ${key}` },
    body: JSON.stringify(args),
    signal: AbortSignal.timeout(8000),
    redirect: "error",
  });
  if (!response.ok) throw new Error(`ledger_rpc_failed_${response.status}`);
  return await response.json();
}

let cachedLedgerToken: string | null = null;
async function expectedToken(): Promise<string> {
  if (cachedLedgerToken) return cachedLedgerToken;
  const value = await rpc("flybrain_eec_ledger_secret", { p_name: "flybrain_eec_ledger_token" });
  if (typeof value !== "string" || value.length < 32) throw new Error("worker_token_unavailable");
  cachedLedgerToken = value;
  return value;
}

Deno.serve(async (request: Request) => {
  if (request.method === "GET") {
    return reply({
      service: "flybrain-eec-ledger", status: "ready", mode: "staging",
      durable_plan_persistence: true, plan_status_readback: true,
      live_agent_execution: false, provider_inference: false,
      external_data_transfer: false, max_spend_usd: 0,
    });
  }
  if (request.method !== "POST") return reply({ error: "method_not_allowed" }, 405);
  if (!(request.headers.get("content-type") ?? "").toLowerCase().includes("application/json")) {
    return reply({ error: "content_type_must_be_application_json" }, 415);
  }
  const length = Number(request.headers.get("content-length") ?? "0");
  if (!Number.isFinite(length) || length < 1 || length > 65536) return reply({ error: "invalid_request_size" }, 413);

  const clientIp = request.headers.get("cf-connecting-ip") ?? "unknown";
  let allowed = false;
  try {
    allowed = await rpc("consume_flybrain_rate_limit", {
      p_key_hash: await sha256("flybrain-eec-ledger:" + clientIp),
      p_limit: 30,
      p_window_seconds: 60,
    }) === true;
  } catch {
    return reply({ error: "rate_limit_unavailable" }, 503);
  }
  if (!allowed) return reply({ error: "rate_limit_exceeded", retry_after_seconds: 60 }, 429);

  let expected = "";
  try { expected = await expectedToken(); }
  catch { return reply({ error: "ledger_auth_unavailable" }, 503); }
  const supplied = request.headers.get("x-flybrain-worker-token") ?? "";
  if (!equalSecret(supplied, expected)) return reply({ error: "unauthorized" }, 401);

  let payload: Record<string, unknown>;
  try { payload = await request.json(); }
  catch { return reply({ error: "invalid_json" }, 400); }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return reply({ error: "invalid_payload" }, 400);

  try {
    if (payload.action === "persist_plan" && Object.keys(payload).sort().join(",") === "action,plan") {
      if (!payload.plan || typeof payload.plan !== "object" || Array.isArray(payload.plan)) return reply({ error: "plan_object_required" }, 422);
      const result = await rpc("flybrain_eec_persist_plan", { p_plan: payload.plan });
      return reply({ status: "ok", result, live_agent_execution: false, external_data_transfer: false });
    }
    if (payload.action === "plan_status" && Object.keys(payload).sort().join(",") === "action,plan_id") {
      if (typeof payload.plan_id !== "string" ||
          !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(payload.plan_id)) {
        return reply({ error: "valid_plan_id_required" }, 422);
      }
      const result = await rpc("flybrain_eec_plan_status", { p_plan_id: payload.plan_id });
      if (!result) return reply({ error: "plan_not_found" }, 404);
      return reply({ status: "ok", plan: result, live_agent_execution: false });
    }
    return reply({ error: "unsupported_action" }, 422);
  } catch {
    return reply({ error: "ledger_operation_failed" }, 503);
  }
});
