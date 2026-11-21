import test from "node:test";
import assert from "node:assert/strict";
import { BROWSER_TOOLS, browserProxyConfigured, proxyBrowserTool } from "./browser-proxy.js";

const env = {
  FLYBRAIN_BROWSER_ACCESS_TOKEN: "client-token-".padEnd(40, "c"),
  BROWSER_AUTOMATION_TOKEN: "backend-token-".padEnd(40, "b"),
  BROWSER_AUTOMATION_MCP_URL: "https://flybrain-browser-staging.example.workers.dev/mcp"
};
const rpc = { jsonrpc: "2.0", id: 7, method: "tools/call", params: { name: "browser_session_snapshot", arguments: { sessionId: "signed-session" } } };

test("browser tools are exposed only with distinct high-entropy client and backend tokens and a workers.dev MCP URL", () => {
  assert.equal(browserProxyConfigured(env), true);
  assert.equal(browserProxyConfigured({ ...env, BROWSER_AUTOMATION_TOKEN: env.FLYBRAIN_BROWSER_ACCESS_TOKEN }), false);
  assert.equal(browserProxyConfigured({ ...env, BROWSER_AUTOMATION_MCP_URL: "http://evil.example/mcp" }), false);
  assert.equal(browserProxyConfigured({ ...env, BROWSER_AUTOMATION_MCP_URL: "https://evil.example/mcp" }), false);
  assert.equal(browserProxyConfigured({ ...env, BROWSER_AUTOMATION_MCP_URL: "https://example.workers.dev/other" }), false);
  assert.equal(BROWSER_TOOLS.length, 8);
});

test("proxy rejects missing or incorrect client bearer token without calling backend", async () => {
  let called = false;
  const request = new Request("https://staging.example/mcp");
  const response = await proxyBrowserTool(request, rpc, env, async () => { called = true; throw new Error("must not call"); });
  const payload = await response.json();
  assert.equal(payload.error.code, -32001);
  assert.equal(called, false);
});

test("proxy forwards approved browser tools with backend token and validates JSON-RPC response", async () => {
  let captured;
  const request = new Request("https://staging.example/mcp", { headers: { authorization: "Bearer " + env.FLYBRAIN_BROWSER_ACCESS_TOKEN } });
  const response = await proxyBrowserTool(request, rpc, env, async (url, init) => {
    captured = { url, init };
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: 7, result: { content: [{ type: "text", text: "ok" }] } }), { status: 200 });
  });
  const payload = await response.json();
  assert.equal(payload.result.content[0].text, "ok");
  assert.equal(captured.url, env.BROWSER_AUTOMATION_MCP_URL);
  assert.equal(captured.init.headers.authorization, "Bearer " + env.BROWSER_AUTOMATION_TOKEN);
  assert.equal(JSON.parse(captured.init.body).params.name, "browser_session_snapshot");
});

test("proxy refuses unlisted tool names and malformed backend replies", async () => {
  const request = new Request("https://staging.example/mcp", { headers: { authorization: "Bearer " + env.FLYBRAIN_BROWSER_ACCESS_TOKEN } });
  const unknown = await proxyBrowserTool(request, { ...rpc, params: { name: "browser_run_task" } }, env, async () => { throw new Error("must not call"); });
  assert.equal((await unknown.json()).error.code, -32602);
  const malformed = await proxyBrowserTool(request, rpc, env, async () => new Response("<html>bad</html>", { status: 200 }));
  assert.equal((await malformed.json()).error.code, -32004);
});

test("proxy cancels an oversized streaming response before buffering it in full", async () => {
  let cancelled = false;
  const request = new Request("https://staging.example/mcp", { headers: { authorization: "Bearer " + env.FLYBRAIN_BROWSER_ACCESS_TOKEN } });
  const response = await proxyBrowserTool(request, rpc, env, async () => new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(6_000_001));
    },
    cancel() {
      cancelled = true;
    }
  }), { status: 200 }));
  const payload = await response.json();
  assert.equal(payload.error.code, -32002);
  assert.equal(cancelled, true);
});
