import test from "node:test";
import assert from "node:assert/strict";
import { BROWSER_TOOLS, browserProxyConfigured, proxyBrowserTool } from "./browser-proxy.js";

const CLIENT_TOKEN = "client-token-".padEnd(40, "c");
const rpc = { jsonrpc: "2.0", id: 7, method: "tools/call", params: { name: "browser_session_snapshot", arguments: { sessionId: "signed-session" } } };

function makeEnv(fetch = async () => new Response(JSON.stringify({ jsonrpc: "2.0", id: 7, result: {} }))) {
  return {
    FLYBRAIN_BROWSER_ACCESS_TOKEN: CLIENT_TOKEN,
    FLYBRAIN_BROWSER_WORKER: { fetch }
  };
}

test("browser tools require a distinct client token and an internal service binding", () => {
  const env = makeEnv();
  assert.equal(browserProxyConfigured(env), true);
  assert.equal(browserProxyConfigured({ ...env, FLYBRAIN_BROWSER_ACCESS_TOKEN: "short" }), false);
  assert.equal(browserProxyConfigured({ FLYBRAIN_BROWSER_ACCESS_TOKEN: CLIENT_TOKEN }), false);
  assert.equal(BROWSER_TOOLS.length, 8);
});

test("proxy rejects missing or incorrect client bearer token without calling the internal Worker", async () => {
  let called = false;
  const env = makeEnv(async () => { called = true; throw new Error("must not call"); });
  const request = new Request("https://staging.example/mcp");
  const response = await proxyBrowserTool(request, rpc, env);
  const payload = await response.json();
  assert.equal(payload.error.code, -32001);
  assert.equal(called, false);
});

test("proxy forwards approved browser tools over the private service binding", async () => {
  let captured;
  const env = makeEnv(async (request) => {
    captured = request;
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: 7, result: { content: [{ type: "text", text: "ok" }] } }), { status: 200 });
  });
  const request = new Request("https://staging.example/mcp", { headers: { authorization: "Bearer " + CLIENT_TOKEN } });
  const response = await proxyBrowserTool(request, rpc, env);
  const payload = await response.json();
  assert.equal(payload.result.content[0].text, "ok");
  assert.equal(captured.url, "https://flybrain-browser-staging.internal/mcp");
  assert.equal(captured.method, "POST");
  assert.equal(captured.headers.get("authorization"), null);
  assert.equal(JSON.parse(await captured.text()).params.name, "browser_session_snapshot");
});

test("proxy refuses unlisted tool names and malformed backend replies", async () => {
  const request = new Request("https://staging.example/mcp", { headers: { authorization: "Bearer " + CLIENT_TOKEN } });
  let called = false;
  const env = makeEnv(async () => { called = true; throw new Error("must not call"); });
  const unknown = await proxyBrowserTool(request, { ...rpc, params: { name: "browser_run_task" } }, env);
  assert.equal((await unknown.json()).error.code, -32602);
  assert.equal(called, false);
  const malformedEnv = makeEnv(async () => new Response("<html>bad</html>", { status: 200 }));
  const malformed = await proxyBrowserTool(request, rpc, malformedEnv);
  assert.equal((await malformed.json()).error.code, -32004);
});

test("proxy cancels an oversized streaming response before buffering it in full", async () => {
  let cancelled = false;
  const request = new Request("https://staging.example/mcp", { headers: { authorization: "Bearer " + CLIENT_TOKEN } });
  const env = makeEnv(async () => new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(6_000_001));
    },
    cancel() {
      cancelled = true;
    }
  }), { status: 200 }));
  const response = await proxyBrowserTool(request, rpc, env);
  const payload = await response.json();
  assert.equal(payload.error.code, -32002);
  assert.equal(cancelled, true);
});
