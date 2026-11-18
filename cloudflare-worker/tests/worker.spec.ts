import { test, expect } from "@playwright/test";

test("health endpoint responds with the Worker service status", async ({ page }) => {
  const response = await page.goto("/health");
  expect(response).not.toBeNull();
  expect(response!.status()).toBe(200);

  const payload = await page.locator("body").innerText();
  const health = JSON.parse(payload);
  expect(health).toMatchObject({
    status: "ok",
    service: "flybrain-cloudflare-worker",
    version: "0.16.0"
  });
});

test("MCP initialize is available without authentication", async ({ request }) => {
  const response = await request.post("/mcp", {
    headers: { "content-type": "application/json" },
    data: {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: { protocolVersion: "2025-03-26" }
    }
  });

  expect(response.status()).toBe(200);
  const payload = await response.json();
  expect(payload).toMatchObject({
    jsonrpc: "2.0",
    id: 1,
    result: {
      protocolVersion: "2025-03-26",
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "flybrain-research-bridge", version: "0.16.0" }
    }
  });
});

test("MCP tools/list exposes research and browser capability tools", async ({ request }) => {
  const response = await request.post("/mcp", {
    headers: { "content-type": "application/json" },
    data: { jsonrpc: "2.0", id: 2, method: "tools/list" }
  });

  expect(response.status()).toBe(200);
  const payload = await response.json();
  const names = payload.result.tools.map((tool: { name: string }) => tool.name);
  expect(names).toEqual(expect.arrayContaining([
    "ask_flybrain",
    "browser_use_status",
    "browser_search",
    "browser_fetch",
    "browser_research",
    "browser_run_task"
  ]));
});

test("MCP tools/call retrieves public FlyBrain project context without authentication", async ({ request }) => {
  const response = await request.post("/mcp", {
    headers: { "content-type": "application/json" },
    data: {
      jsonrpc: "2.0",
      id: 3,
      method: "tools/call",
      params: { name: "ask_flybrain", arguments: { question: "FlyBrain URCAL research platform" } }
    },
    timeout: 30000
  });

  expect(response.status()).toBe(200);
  const payload = await response.json();
  expect(payload.result.structuredContent).toMatchObject({
    status: "context_only",
    external_data_transfer: false
  });
  expect(payload.result.structuredContent.research_context.length).toBeGreaterThan(0);
});
test("browser automation tools require a separate bearer token", async ({ request }) => {
  const response = await request.post("/mcp", {
    headers: { "content-type": "application/json" },
    data: {
      jsonrpc: "2.0",
      id: 4,
      method: "tools/call",
      params: { name: "browser_use_status", arguments: {} }
    }
  });

  expect(response.status()).toBe(200);
  const payload = await response.json();
  expect(payload.error).toMatchObject({
    code: -32001,
    message: "Browser automation access is unauthorized"
  });
});
