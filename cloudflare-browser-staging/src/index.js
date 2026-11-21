const VERSION = "0.1.1-staging";
const MAX_BODY = 65536;
const MAX_TEXT = 24000;
const SESSION_KEEPALIVE_MS = 60000;

const HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "POST, GET, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, accept"
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: HEADERS });
}
function rpcError(id, code, message) {
  return json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}
function textResult(value, extra = []) {
  const serialized = typeof value === "string" ? value : JSON.stringify(value);
  return { content: [{ type: "text", text: serialized }, ...extra], isError: false };
}
function validHostPattern(pattern) {
  if (typeof pattern !== "string" || !pattern || pattern.length > 253) return false;
  if (pattern.includes("://") || pattern.includes("/") || pattern.includes(":") || pattern.includes("@")) return false;
  const wildcardCount = [...pattern].filter((char) => char === "*").length;
  if (pattern === "*" || wildcardCount > 1 || (wildcardCount === 1 && !pattern.startsWith("*."))) return false;
  const hostname = pattern.startsWith("*.") ? pattern.slice(2) : pattern;
  const labels = hostname.split(".");
  if (labels.length < 2 || labels.some((label) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label))) return false;
  if (/^(?:localhost|.*\.(?:local|internal|localhost|test))$/i.test(hostname)) return false;
  if (labels.every((label) => /^\d+$/.test(label))) return false;
  return true;
}
function hostAllowed(host, patterns) {
  return patterns.some((pattern) => {
    if (pattern === "*") return true;
    if (pattern.startsWith("*.")) return host.endsWith(pattern.slice(1)) && host !== pattern.slice(2);
    if (pattern.startsWith("*")) return host.endsWith(pattern.slice(1));
    return host === pattern;
  });
}
function validateUrl(value, patterns) {
  let url;
  try { url = new URL(value); } catch { throw new Error("Invalid URL"); }
  if (url.protocol !== "https:") throw new Error("Only HTTPS URLs are allowed");
  if (url.username || url.password) throw new Error("URLs containing credentials are not allowed");
  if (!hostAllowed(url.hostname.toLowerCase(), patterns)) throw new Error("URL hostname is not covered by the session allowlist");
  return url.toString();
}
function validateAllowlist(value) {
  if (!Array.isArray(value) || value.length < 1 || value.length > 50 || !value.every(validHostPattern)) {
    throw new Error("allowedDomains must contain 1–50 valid hostname patterns");
  }
  const normalized = [...new Set(value.map((v) => v.toLowerCase()))];
  if (normalized.join(",").length > 2500) {
    throw new Error("Combined allowedDomains length must not exceed 2500 characters");
  }
  return normalized;
}

function base64UrlEncode(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).split("+").join("-").split("/").join("_").replace(/=+$/g, "");
}
function base64UrlDecode(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) throw new Error("Invalid session token encoding");
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}
async function sessionSigningKey(env) {
  if (typeof env.FLYBRAIN_BROWSER_API_TOKEN !== "string" || env.FLYBRAIN_BROWSER_API_TOKEN.length < 32) {
    throw new Error("Session signing is not configured");
  }
  return crypto.subtle.importKey(
    "raw", new TextEncoder().encode(env.FLYBRAIN_BROWSER_API_TOKEN),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]
  );
}
async function signSessionToken(env, sessionId, allowedDomains, expiresAt = Date.now() + 900000) {
  const payload = {
    version: 1,
    sessionId,
    allowedDomains: validateAllowlist(allowedDomains),
    expiresAt
  };
  const encoded = base64UrlEncode(new TextEncoder().encode(JSON.stringify(payload)));
  const key = await sessionSigningKey(env);
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(encoded));
  const token = encoded + "." + base64UrlEncode(new Uint8Array(signature));
  if (token.length > 4096) throw new Error("Browser session token exceeds the safe size limit");
  return token;
}
async function readSessionToken(env, token) {
  if (typeof token !== "string" || token.length > 4096) throw new Error("Invalid or expired browser session token");
  const parts = token.split(".");
  if (parts.length !== 2) throw new Error("Invalid browser session token");
  const key = await sessionSigningKey(env);
  const signature = base64UrlDecode(parts[1]);
  const valid = await crypto.subtle.verify("HMAC", key, signature, new TextEncoder().encode(parts[0]));
  if (!valid) throw new Error("Browser session token signature is invalid");
  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(base64UrlDecode(parts[0])));
  } catch {
    throw new Error("Browser session token payload is invalid");
  }
  if (payload.version !== 1 || typeof payload.sessionId !== "string" ||
      !payload.sessionId || payload.sessionId.length > 512 ||
      !Number.isFinite(payload.expiresAt) || payload.expiresAt <= Date.now()) {
    throw new Error("Browser session token is expired or invalid");
  }
  return { sessionId: payload.sessionId, allowedDomains: validateAllowlist(payload.allowedDomains) };
}
async function resolveSessionId(env, token) {
  return (await readSessionToken(env, token)).sessionId;
}

let nextCommandId = 0;
async function connectCdp(env, sessionId) {
  const session = await env.BROWSER.getSession(sessionId);
  if (!session) throw new Error("Browser session not found or expired");
  const connection = await env.BROWSER.connectSession(sessionId);
  const response = await connection.webSocket.fetch("https://browser-binding.invalid", {
    headers: { Upgrade: "websocket" }
  });
  if (!response.webSocket) throw new Error("Browser Run did not provide a CDP WebSocket");
  const socket = response.webSocket;
  socket.accept();
  const targets = await sendCdp(socket, "Target.getTargets");
  const page = (targets.targetInfos || []).find((target) => target.type === "page");
  if (!page) {
    socket.close();
    throw new Error("No page target exists in this browser session");
  }
  const attached = await sendCdp(socket, "Target.attachToTarget", { targetId: page.targetId, flatten: true });
  return { socket, sessionId: attached.sessionId, targetId: page.targetId };
}
function sendCdp(socket, method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++nextCommandId;
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error("CDP command timed out: " + method));
    }, 12000);
    const cleanup = () => {
      clearTimeout(timeout);
      socket.removeEventListener("message", onMessage);
      socket.removeEventListener("close", onClose);
    };
    const onClose = () => {
      cleanup();
      reject(new Error("CDP WebSocket closed"));
    };
    const onMessage = (event) => {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (message.id !== id) return;
      cleanup();
      if (message.error) reject(new Error(message.error.message || "CDP error"));
      else resolve(message.result || {});
    };
    socket.addEventListener("message", onMessage);
    socket.addEventListener("close", onClose);
    try {
      const command = { id, method, params };
      if (sessionId) command.sessionId = sessionId;
      socket.send(JSON.stringify(command));
    } catch (error) {
      cleanup();
      reject(error);
    }
  });
}
async function withPage(env, sessionId, operation) {
  const cdp = await connectCdp(env, sessionId);
  try {
    await sendCdp(cdp.socket, "Page.enable", {}, cdp.sessionId);
    return await operation(cdp);
  } finally {
    try { cdp.socket.close(); } catch {}
  }
}
async function evaluate(cdp, expression) {
  const result = await sendCdp(cdp.socket, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
    userGesture: true
  }, cdp.sessionId);
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Page evaluation failed");
  return result.result?.value;
}
async function waitForReady(cdp) {
  for (let i = 0; i < 8; i++) {
    const state = await evaluate(cdp, "document.readyState");
    if (state === "interactive" || state === "complete") return state;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return "loading";
}
async function callTool(name, args, env) {
  switch (name) {
    case "browser_session_open": {
      const allowedDomains = validateAllowlist(args.allowedDomains);
      const url = validateUrl(args.url, allowedDomains);
      const session = await env.BROWSER.acquire({
        targets: true,
        keepAlive: SESSION_KEEPALIVE_MS,
        guardrails: { allowedDomains }
      });
      try {
        const result = await withPage(env, session.sessionId, async (cdp) => {
          await sendCdp(cdp.socket, "Page.navigate", { url }, cdp.sessionId);
          const readyState = await waitForReady(cdp);
          const title = await evaluate(cdp, "document.title");
          return { title, readyState };
        });
        const liveView = await env.BROWSER.getLiveView(session.sessionId);
        const sessionToken = await signSessionToken(env, session.sessionId, allowedDomains);
        return textResult({
          status: "opened",
          sessionId: sessionToken,
          targetId: session.targets?.find((t) => t.type === "page")?.targetId ?? null,
          url,
          title: result.title || "",
          readyState: result.readyState,
          liveView
        });
      } catch (error) {
        await env.BROWSER.closeSession(session.sessionId).catch(() => {});
        throw error;
      }
    }
    case "browser_session_navigate": {
      const session = await readSessionToken(env, args.sessionId);
      const url = validateUrl(args.url, session.allowedDomains);
      const result = await withPage(env, session.sessionId, async (cdp) => {
        await sendCdp(cdp.socket, "Page.navigate", { url }, cdp.sessionId);
        const readyState = await waitForReady(cdp);
        return { url: await evaluate(cdp, "location.href"), title: await evaluate(cdp, "document.title"), readyState };
      });
      return textResult(result);
    }
    case "browser_session_snapshot": {
      const result = await withPage(env, await resolveSessionId(env, args.sessionId), async (cdp) => ({
        url: await evaluate(cdp, "location.href"),
        title: await evaluate(cdp, "document.title"),
        text: String(await evaluate(cdp, "document.body ? document.body.innerText : ''") || "").slice(0, MAX_TEXT),
        html: args.includeHtml ? String(await evaluate(cdp, "document.documentElement.outerHTML") || "").slice(0, MAX_TEXT) : undefined
      }));
      return textResult(result);
    }
    case "browser_session_click": {
      const sessionId = await resolveSessionId(env, args.sessionId);
      if (args.allowSideEffects !== undefined && typeof args.allowSideEffects !== "boolean") throw new Error("allowSideEffects must be boolean");
      if (args.allowSideEffects !== true) return textResult({ status: "approval_required", message: "Explicit approval is required before clicking a page element.", steps: 0 });
      if (typeof args.selector !== "string" || args.selector.length > 1000) throw new Error("A CSS selector is required");
      const result = await withPage(env, sessionId, async (cdp) => evaluate(cdp,
        `(() => { const el = document.querySelector(${JSON.stringify(args.selector)}); if (!el) return {clicked:false,reason:"not_found"}; el.click(); return {clicked:true,tag:el.tagName,text:(el.innerText||el.getAttribute("aria-label")||"").slice(0,200)}; })()`
      ));
      return textResult(result);
    }
    case "browser_session_type": {
      const sessionId = await resolveSessionId(env, args.sessionId);
      if (args.allowSideEffects !== undefined && typeof args.allowSideEffects !== "boolean") throw new Error("allowSideEffects must be boolean");
      if (args.allowSideEffects !== true) return textResult({ status: "approval_required", message: "Explicit approval is required before typing into a page.", steps: 0 });
      if (typeof args.selector !== "string" || args.selector.length > 1000 || typeof args.text !== "string" || args.text.length > 10000) throw new Error("A valid selector and text are required");
      const result = await withPage(env, sessionId, async (cdp) => evaluate(cdp,
        `(() => { const el = document.querySelector(${JSON.stringify(args.selector)}); if (!el) return {typed:false,reason:"not_found"}; el.focus(); const setter = Object.getOwnPropertyDescriptor(el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, "value")?.set; if (setter && "value" in el) setter.call(el, ${JSON.stringify(args.text)}); else el.textContent = ${JSON.stringify(args.text)}; el.dispatchEvent(new Event("input",{bubbles:true})); el.dispatchEvent(new Event("change",{bubbles:true})); return {typed:true}; })()`
      ));
      return textResult(result);
    }
    case "browser_session_press": {
      const sessionId = await resolveSessionId(env, args.sessionId);
      if (args.allowSideEffects !== undefined && typeof args.allowSideEffects !== "boolean") throw new Error("allowSideEffects must be boolean");
      if (args.allowSideEffects !== true) return textResult({ status: "approval_required", message: "Explicit approval is required before sending a keypress.", steps: 0 });
      const keyMap = { ENTER: "Enter", TAB: "Tab", ESCAPE: "Escape", BACKSPACE: "Backspace", ARROWDOWN: "ArrowDown", ARROWUP: "ArrowUp", ARROWLEFT: "ArrowLeft", ARROWRIGHT: "ArrowRight", SPACE: " " };
      const key = keyMap[String(args.key || "").toUpperCase()];
      if (!key) throw new Error("Supported keys: ENTER, TAB, ESCAPE, BACKSPACE, ARROWDOWN, ARROWUP, ARROWLEFT, ARROWRIGHT, SPACE");
      await withPage(env, sessionId, async (cdp) => {
        await sendCdp(cdp.socket, "Input.dispatchKeyEvent", { type: "keyDown", key }, cdp.sessionId);
        await sendCdp(cdp.socket, "Input.dispatchKeyEvent", { type: "keyUp", key }, cdp.sessionId);
      });
      return textResult({ pressed: key });
    }
    case "browser_session_screenshot": {
      const result = await withPage(env, await resolveSessionId(env, args.sessionId), async (cdp) => sendCdp(cdp.socket, "Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false,
        fromSurface: true
      }, cdp.sessionId));
      if (!result.data || result.data.length > 4_000_000) throw new Error("Screenshot is empty or exceeds the 4 MB response limit");
      return textResult({ mimeType: "image/png", bytes: Math.floor(result.data.length * 0.75) }, [
        { type: "image", data: result.data, mimeType: "image/png" }
      ]);
    }
    case "browser_session_close": {
      const sessionId = await resolveSessionId(env, args.sessionId);
      const result = await env.BROWSER.closeSession(sessionId);
      return textResult({ status: result });
    }
    default:
      throw new Error("Unknown tool");
  }
}

const TOOLS = [
  { name: "browser_session_open", description: "Start a guarded remote Chromium session. Supply a URL and explicit hostname allowlist. Returns a session ID and Live View URL.", inputSchema: { type: "object", properties: { url: { type: "string" }, allowedDomains: { type: "array", items: { type: "string" }, minItems: 1, maxItems: 50 } }, required: ["url", "allowedDomains"], additionalProperties: false }, annotations: { readOnlyHint: false, openWorldHint: true } },
  { name: "browser_session_navigate", description: "Navigate an existing browser session. The session's original Cloudflare hostname guardrails remain enforced.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, url: { type: "string" } }, required: ["sessionId", "url"], additionalProperties: false } },
  { name: "browser_session_snapshot", description: "Read the current page URL, title, visible text, and optionally a bounded HTML excerpt.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, includeHtml: { type: "boolean" } }, required: ["sessionId"], additionalProperties: false }, annotations: { readOnlyHint: true } },
  { name: "browser_session_click", description: "Click the first element matching a CSS selector. Requires allowSideEffects=true as explicit approval.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, selector: { type: "string" }, allowSideEffects: { type: "boolean", default: false } }, required: ["sessionId", "selector"], additionalProperties: false } },
  { name: "browser_session_type", description: "Type text into an input, textarea, or editable element selected by CSS selector. Requires allowSideEffects=true as explicit approval.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, selector: { type: "string" }, text: { type: "string" }, allowSideEffects: { type: "boolean", default: false } }, required: ["sessionId", "selector", "text"], additionalProperties: false } },
  { name: "browser_session_press", description: "Press a supported keyboard key in the active page. Requires allowSideEffects=true as explicit approval.", inputSchema: { type: "object", properties: { sessionId: { type: "string" }, key: { type: "string" }, allowSideEffects: { type: "boolean", default: false } }, required: ["sessionId", "key"], additionalProperties: false } },
  { name: "browser_session_screenshot", description: "Capture the current browser viewport as a PNG image.", inputSchema: { type: "object", properties: { sessionId: { type: "string" } }, required: ["sessionId"], additionalProperties: false }, annotations: { readOnlyHint: true } },
  { name: "browser_session_close", description: "Close a browser session and release its Browser Run usage.", inputSchema: { type: "object", properties: { sessionId: { type: "string" } }, required: ["sessionId"], additionalProperties: false } }
];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: HEADERS });
    if (url.pathname === "/health" && request.method === "GET") {
      return json({ status: "ok", service: "flybrain-browser-staging", version: VERSION, browserBinding: Boolean(env.BROWSER), authenticationConfigured: Boolean(env.FLYBRAIN_BROWSER_API_TOKEN), mode: "guarded-browser-sessions" });
    }
    if (url.pathname !== "/mcp") return json({ error: "not_found" }, 404);
    if (request.method !== "POST") return new Response(null, { status: 405, headers: { ...HEADERS, allow: "POST, OPTIONS" } });
    if (!env.FLYBRAIN_BROWSER_API_TOKEN) return json({ error: "server_auth_not_configured" }, 503);
    const auth = request.headers.get("authorization") || "";
    const supplied = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    const expected = env.FLYBRAIN_BROWSER_API_TOKEN;
    if (!supplied || supplied.length > 4096) return json({ error: "unauthorized" }, 401);
    const encoder = new TextEncoder();
    const [suppliedDigest, expectedDigest] = await Promise.all([
      crypto.subtle.digest("SHA-256", encoder.encode(supplied)),
      crypto.subtle.digest("SHA-256", encoder.encode(expected))
    ]);
    const a = new Uint8Array(suppliedDigest);
    const b = new Uint8Array(expectedDigest);
    let mismatch = 0;
    for (let i = 0; i < a.length; i++) mismatch |= a[i] ^ b[i];
    if (mismatch !== 0) return json({ error: "unauthorized" }, 401);
    if (!(request.headers.get("content-type") || "").toLowerCase().includes("application/json")) return json({ error: "content_type_must_be_application_json" }, 415);
    let rpc;
    try {
      const rawBody = await request.arrayBuffer();
      if (rawBody.byteLength > MAX_BODY) return json({ error: "request_too_large" }, 413);
      rpc = JSON.parse(new TextDecoder().decode(rawBody));
    } catch { return json({ error: "invalid_json" }, 400); }
    if (!rpc || rpc.jsonrpc !== "2.0" || typeof rpc.method !== "string") return json({ error: "invalid_json_rpc_request" }, 400);
    if (rpc.method === "initialize") return json({ jsonrpc: "2.0", id: rpc.id, result: {
      protocolVersion: "2025-03-26",
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "flybrain-browser-staging", version: VERSION },
      instructions: "Authenticated interactive browser tools. Every new browser session requires an explicit hostname allowlist enforced by Browser Run guardrails. Close sessions when finished. Never send passwords, API keys, or private tokens to untrusted pages."
    }});
    if (rpc.method === "ping") return json({ jsonrpc: "2.0", id: rpc.id, result: {} });
    if (rpc.method === "tools/list") return json({ jsonrpc: "2.0", id: rpc.id, result: { tools: TOOLS } });
    if (rpc.method === "notifications/initialized") return new Response(null, { status: 202, headers: HEADERS });
    if (rpc.method === "tools/call") {
      const name = rpc.params?.name;
      const args = rpc.params?.arguments || {};
      try {
        const result = await callTool(name, args, env);
        return json({ jsonrpc: "2.0", id: rpc.id, result });
      } catch (error) {
        return json({ jsonrpc: "2.0", id: rpc.id, result: {
          content: [{ type: "text", text: error instanceof Error ? error.message : "Browser operation failed" }],
          isError: true
        }});
      }
    }
    return rpcError(rpc.id, -32601, "Method not found");
  }
};

export { validateUrl, hostAllowed, signSessionToken, readSessionToken, callTool };
