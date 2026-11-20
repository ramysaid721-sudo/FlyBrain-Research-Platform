const HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};
function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: HEADERS });
}
function equalSecret(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
async function rpc(name: string, args: Record<string, unknown>) {
  const base = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!base || !key) throw new Error("worker_configuration_missing");
  const response = await fetch(`${base}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: { "content-type": "application/json", apikey: key, authorization: `Bearer ${key}` },
    body: JSON.stringify(args),
    signal: AbortSignal.timeout(8000),
    redirect: "error",
  });
  if (!response.ok) throw new Error(`database_${name}_failed_${response.status}`);
  return await response.json();
}
async function readWorkerToken(): Promise<string> {
  const value = await rpc("flybrain_worker_secret", { p_name: "flybrain_worker_token" });
  if (typeof value !== "string" || value.length < 32) throw new Error("worker_token_unavailable");
  return value;
}
class CrossrefRateLimitError extends Error {
  retryDelaySeconds: number;
  constructor(delay: number) {
    super("crossref_http_429");
    this.name = "CrossrefRateLimitError";
    this.retryDelaySeconds = delay;
  }
}
function retryDelayFromHeader(value: string | null, attempt: number): number {
  let seconds: number | null = null;
  if (value) {
    const trimmed = value.trim();
    if (/^\d+$/.test(trimmed)) {
      seconds = Number(trimmed);
    } else {
      const dateMs = Date.parse(trimmed);
      if (Number.isFinite(dateMs)) seconds = Math.ceil((dateMs - Date.now()) / 1000);
    }
  }
  const fallback = Math.min(900, 120 * (2 ** Math.max(0, attempt - 1)));
  const requested = seconds !== null && Number.isFinite(seconds) ? seconds : fallback;
  return Math.min(900, Math.max(60, Math.ceil(requested)));
}
async function runResearchSearch(payload: Record<string, unknown>, attempt: number) {
  if (Object.keys(payload).sort().join(",") !== "page_size,query" ||
      typeof payload.query !== "string" || !payload.query.trim() || payload.query.length > 400 ||
      !Number.isInteger(payload.page_size) || (payload.page_size as number) < 1 || (payload.page_size as number) > 10) {
    throw new Error("invalid_task_payload");
  }
  const query = payload.query.trim();
  const params = new URLSearchParams({ "query.bibliographic": query, rows: String(payload.page_size) });
  const response = await fetch(`https://api.crossref.org/works?${params.toString()}`, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(10000),
    redirect: "error",
  });
  if (response.status === 429) {
    throw new CrossrefRateLimitError(retryDelayFromHeader(response.headers.get("Retry-After"), attempt));
  }
  if (!response.ok) throw new Error(`crossref_http_${response.status}`);
  let body: any;
  try {
    body = await response.json();
  } catch {
    throw new Error("crossref_invalid_json");
  }
  if (!body || typeof body !== "object" || Array.isArray(body) ||
      body.status !== "ok" || !body.message || typeof body.message !== "object" ||
      Array.isArray(body.message) || !Array.isArray(body.message.items) ||
      !Number.isFinite(body.message["total-results"]) || body.message["total-results"] < 0 ||
      body.message.items.some((item: any) => !item || typeof item !== "object" || Array.isArray(item))) {
    throw new Error("crossref_invalid_response");
  }
  const message = body.message;
  const rows = message.items;
  const results = rows.slice(0, payload.page_size as number).map((item: any) => {
    const dateParts = item["published-print"]?.["date-parts"]?.[0] ??
      item["published-online"]?.["date-parts"]?.[0] ??
      item.published?.["date-parts"]?.[0] ?? [];
    const year = Array.isArray(dateParts) && Number.isInteger(dateParts[0]) ? dateParts[0] : null;
    const authors = Array.isArray(item.author)
      ? item.author.slice(0, 8)
          .filter((a: any) => a && typeof a === "object" && !Array.isArray(a))
          .map((a: any) => [a.given, a.family]
            .filter((v: any) => typeof v === "string" && v.trim())
            .join(" "))
          .filter(Boolean).join(", ")
      : "";
    const title = Array.isArray(item.title) && typeof item.title[0] === "string" ? item.title[0] : "";
    const journal = Array.isArray(item["container-title"]) && typeof item["container-title"][0] === "string"
      ? item["container-title"][0] : "";
    const doi = typeof item.DOI === "string" ? item.DOI : null;
    const url = typeof item.URL === "string" ? item.URL : (doi ? `https://doi.org/${doi}` : null);
    return {
      title,
      authors,
      journal,
      year,
      doi,
      type: typeof item.type === "string" ? item.type : null,
      abstract: typeof item.abstract === "string" ? item.abstract.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 1200) : "",
      url,
    };
  });
  return { provider: "Crossref", query, hit_count: Number(message["total-results"] ?? 0), returned: results.length, results };
}
Deno.serve(async (request: Request) => {
  if (request.method === "GET") return reply({ service: "flybrain-task-worker", status: "ready", mode: "staging", external_provider: "Crossref-only", lease_fencing: true, retry_after_429: true });
  if (request.method !== "POST") return reply({ error: "method_not_allowed" }, 405);
  const supplied = request.headers.get("x-flybrain-worker-token") ?? "";
  let expected = "";
  try { expected = await readWorkerToken(); } catch { return reply({ error: "worker_auth_unavailable" }, 503); }
  if (!equalSecret(supplied, expected)) return reply({ error: "unauthorized" }, 401);
  let claimed: any;
  try { claimed = await rpc("flybrain_claim_task", { p_visibility_timeout: 60 }); }
  catch { return reply({ error: "queue_unavailable" }, 503); }
  if (!claimed) return reply({ status: "idle", processed: false });
  const taskId = claimed.task_id;
  const messageId = claimed.message_id;
  const claimToken = claimed.claim_token;
  const attempt = Number.isInteger(claimed.attempts) ? claimed.attempts : 1;
  if (typeof claimToken !== "string") return reply({ error: "invalid_claim" }, 500);
  try {
    if (claimed.task_type !== "research_search" || !claimed.payload || typeof claimed.payload !== "object") throw new Error("unsupported_task_type");
    const result = await runResearchSearch(claimed.payload, attempt);
    const completed = await rpc("flybrain_complete_task", {
      p_task_id: taskId, p_message_id: messageId, p_claim_token: claimToken, p_result: result
    });
    if (completed !== true) return reply({ error: "task_completion_conflict", task_id: taskId }, 409);
    return reply({ status: "completed", processed: true, task_id: taskId, task_type: claimed.task_type });
  } catch (error) {
    const code = error instanceof Error ? error.message.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80) : "task_failed";
    try {
      if (error instanceof CrossrefRateLimitError) {
        const outcome = await rpc("flybrain_defer_task", {
          p_task_id: taskId, p_message_id: messageId, p_claim_token: claimToken,
          p_error_code: code, p_retry_delay: error.retryDelaySeconds
        });
        if (!outcome || outcome.updated !== true) {
          return reply({
            error: "rate_limit_deferral_conflict",
            task_id: taskId,
            outcome
          }, 409);
        }
        return reply({
          status: "rate_limited_deferred", task_id: taskId, outcome,
          retry_delay_seconds: error.retryDelaySeconds, attempt
        }, 202);
      }
      const outcome = await rpc("flybrain_fail_task", {
        p_task_id: taskId, p_message_id: messageId, p_claim_token: claimToken, p_error_code: code
      });
      if (!outcome || outcome.updated !== true) {
        return reply({
          error: "task_failure_state_conflict",
          task_id: taskId,
          outcome
        }, 409);
      }
      return reply({ status: "failed_or_requeued", task_id: taskId, outcome, error_code: code }, 502);
    } catch {
      return reply({ error: "task_failed_and_status_update_failed", task_id: taskId }, 503);
    }
  }
});