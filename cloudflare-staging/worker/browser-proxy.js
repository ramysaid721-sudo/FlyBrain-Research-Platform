const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, accept, mcp-session-id, last-event-id"
};

export const BROWSER_TOOLS = [
  { name: "browser_session_open", description: "Start a guarded Cloudflare Chromium session. Supply a URL and explicit hostname allowlist. Returns a signed session handle and Live View URL.", inputSchema: { type: "object", properties: { url: { type: "string" }, allowedDomains: { type: "array", items: { type: "string" }, minItems: 1, maxItems: 50 } }, required: ["url", "allowedDomains"], additionalProperties: false }, annotations: { readOnlyHint: false, openWorldHint: true } },
  { name: "browser_session_navigate", description: "Navigate an existing browser session within its original hostname allowlist.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, url: { type: "string" } }, required: ["sessionId", "url"], additionalProperties: false }, annotations: { readOnlyHint: false, openWorldHint: true } },
  { name: "browser_session_snapshot", description: "Read current URL, title, visible text, and optionally a bounded HTML excerpt.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, includeHtml: { type: "boolean" } }, required: ["sessionId"], additionalProperties: false }, annotations: { readOnlyHint: true, openWorldHint: false } },
  { name: "browser_session_click", description: "Click a page element. Explicit allowSideEffects=true approval is required for every click.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, selector: { type: "string" }, allowSideEffects: { type: "boolean", default: false } }, required: ["sessionId", "selector"], additionalProperties: false }, annotations: { readOnlyHint: false, openWorldHint: true } },
  { name: "browser_session_type", description: "Type into a page element. Explicit allowSideEffects=true approval is required.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, selector: { type: "string" }, text: { type: "string" }, allowSideEffects: { type: "boolean", default: false } }, required: ["sessionId", "selector", "text"], additionalProperties: false }, annotations: { readOnlyHint: false, openWorldHint: true } },
  { name: "browser_session_press", description: "Send a keyboard key. Explicit allowSideEffects=true approval is required.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, key: { type: "string" }, allowSideEffects: { type: "boolean", default: false } }, required: ["sessionId", "key"], additionalProperties: false }, annotations: { readOnlyHint: false, openWorldHint: true } },
  { name: "browser_session_screenshot", description: "Capture the current browser viewport as a PNG image.", inputSchema: { type: "object", properties: { sessionId: { type: "string" } }, required: ["sessionId"], additionalProperties: false }, annotations: { readOnlyHint: true, openWorldHint: false } },
  { name: "browser_session_close", description: "Close a browser session and release Browser Run usage.", inputSchema: { type: "object", properties: { sessionId: { type: "string" } }, required: ["sessionId"], additionalProperties: false }, annotations: { readOnlyHint: false, openWorldHint: false } }
];

export function browserProxyConfigured(env = {}) {
  const client = env.FLYBRAIN_BROWSER_ACCESS_TOKEN;
  const service = env.FLYBRAIN_BROWSER_WORKER;
  return typeof client === "string" && client.length >= 32 &&
    service !== null && typeof service === "object" &&
    typeof service.fetch === "function";
}

function errorResponse(id, code, message) {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id: id ?? null, error: { code, message } }), {
    status: 200, headers: JSON_HEADERS
  });
}

async function readBoundedText(response, maxBytes) {
  if (!response.body) return "";
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  let totalBytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalBytes += value.byteLength;
      if (totalBytes > maxBytes) {
        await reader.cancel("Response exceeded configured size limit").catch(() => {});
        return null;
      }
      text += decoder.decode(value, { stream: true });
    }
    return text + decoder.decode();
  } finally {
    reader.releaseLock();
  }
}

async function constantTimeMatch(supplied, expected) {
  if (typeof supplied !== "string" || !supplied || typeof expected !== "string" || !expected) return false;
  const encoder = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(supplied)),
    crypto.subtle.digest("SHA-256", encoder.encode(expected))
  ]);
  const left = new Uint8Array(a);
  const right = new Uint8Array(b);
  let mismatch = 0;
  for (let i = 0; i < left.length; i++) mismatch |= left[i] ^ right[i];
  return mismatch === 0;
}

export async function proxyBrowserTool(request, rpc, env) {
  const name = rpc?.params?.name;
  if (!BROWSER_TOOLS.some((tool) => tool.name === name)) {
    return errorResponse(rpc?.id, -32602, "Unknown browser session tool");
  }
  if (!browserProxyConfigured(env)) {
    return errorResponse(rpc?.id, -32000, "Browser Run service binding or client token is not configured");
  }
  const supplied = (request.headers.get("authorization") || "").replace(/^Bearer\\s+/i, "");
  if (!await constantTimeMatch(supplied, env.FLYBRAIN_BROWSER_ACCESS_TOKEN)) {
    return errorResponse(rpc?.id, -32001, "Browser automation access is unauthorized");
  }
  try {
    const internalRequest = new Request("https://flybrain-browser-staging.internal/mcp", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(rpc),
      signal: AbortSignal.timeout(45000)
    });
    const upstream = await env.FLYBRAIN_BROWSER_WORKER.fetch(internalRequest);
    if (!upstream.ok) return errorResponse(rpc.id, -32002, "Browser Run backend returned HTTP " + upstream.status);
    const body = await readBoundedText(upstream, 6_000_000);
    if (body === null) return errorResponse(rpc.id, -32002, "Browser Run backend response exceeded the safe response limit");
    let payload;
    try { payload = JSON.parse(body); } catch { return errorResponse(rpc.id, -32004, "Browser Run backend returned invalid JSON"); }
    if (!payload || payload.jsonrpc !== "2.0" || payload.id !== rpc.id) {
      return errorResponse(rpc.id, -32004, "Browser Run backend returned an invalid JSON-RPC response");
    }
    return new Response(JSON.stringify(payload), { status: 200, headers: JSON_HEADERS });
  } catch {
    return errorResponse(rpc.id, -32003, "Browser Run service binding is unreachable or timed out");
  }
}
