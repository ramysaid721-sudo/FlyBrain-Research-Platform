import { test, expect } from "@playwright/test";

const testToken = "playwright-local-test-token";

test("health endpoint responds with the Worker service status", async ({ page }) => {
  const response = await page.goto("/health");
  expect(response).not.toBeNull();
  expect(response!.status()).toBe(200);

  const payload = await page.locator("body").innerText();
  const health = JSON.parse(payload);
  expect(health).toMatchObject({
    status: "ok",
    service: "flybrain-cloudflare-worker",
    version: "0.15.0"
  });
});

test("MCP endpoint rejects requests without bearer authentication", async ({ request }) => {
  const response = await request.post("/mcp", {
    headers: { "content-type": "application/json" },
    data: {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: { protocolVersion: "2025-03-26" }
    }
  });

  expect(response.status()).toBe(401);
});

test("MCP initialize returns the FlyBrain bridge capabilities with valid authentication", async ({ request }) => {
  const response = await request.post("/mcp", {
    headers: {
      authorization: `Bearer ${testToken}`,
      "content-type": "application/json"
    },
    data: {
      jsonrpc: "2.0",
      id: 2,
      method: "initialize",
      params: { protocolVersion: "2025-03-26" }
    }
  });

  expect(response.status()).toBe(200);
  const payload = await response.json();
  expect(payload).toMatchObject({
    jsonrpc: "2.0",
    id: 2,
    result: {
      protocolVersion: "2025-03-26",
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "flybrain-research-bridge", version: "0.15.0" }
    }
  });
});
