import test from "node:test";
import assert from "node:assert/strict";
import { callTool, readSessionToken, signSessionToken, validateUrl } from "./index.js";

const env = { FLYBRAIN_BROWSER_API_TOKEN: "test-session-signing-key-".padEnd(40, "x") };

test("session token carries the original allowlist and verifies its signature", async () => {
  const token = await signSessionToken(env, "browser-session-123", ["example.com"]);
  const context = await readSessionToken(env, token);
  assert.equal(context.sessionId, "browser-session-123");
  assert.deepEqual(context.allowedDomains, ["example.com"]);

  const [payloadPart, signaturePart] = token.split(".");
  const payload = JSON.parse(Buffer.from(payloadPart, "base64url").toString("utf8"));
  payload.allowedDomains = ["attacker.example"];
  const tampered = Buffer.from(JSON.stringify(payload)).toString("base64url") + "." + signaturePart;
  await assert.rejects(() => readSessionToken(env, tampered), /signature is invalid/);
});

test("expired session tokens are rejected", async () => {
  const token = await signSessionToken(env, "expired-session", ["example.com"], Date.now() - 1);
  await assert.rejects(() => readSessionToken(env, token), /expired or invalid/);
});

test("interactive URL validation rejects HTTP even when the hostname is allowlisted", () => {
  assert.throws(() => validateUrl("http://example.com/", ["example.com"]), /Only HTTPS/);
});

test("URL validation enforces exact and wildcard hostname allowlists", () => {
  assert.equal(validateUrl("https://example.com/path", ["example.com"]), "https://example.com/path");
  assert.equal(validateUrl("https://docs.example.com", ["*.example.com"]), "https://docs.example.com/");
  assert.throws(() => validateUrl("https://evil.example.net", ["*.example.com"]), /allowlist/);
  assert.throws(() => validateUrl("https://user:pass@example.com", ["example.com"]), /credentials/);
});

test("browser navigation rejects a hostname outside the signed session allowlist before CDP access", async () => {
  let browserTouched = false;
  const mockEnv = {
    ...env,
    BROWSER: {
      getSession() { browserTouched = true; throw new Error("should not reach Browser Run"); },
      connectSession() { browserTouched = true; throw new Error("should not reach Browser Run"); }
    }
  };
  const token = await signSessionToken(mockEnv, "browser-session-123", ["example.com"]);
  await assert.rejects(
    () => callTool("browser_session_navigate", {
      sessionId: token, url: "https://attacker.example/"
    }, mockEnv),
    /allowlist/
  );
  assert.equal(browserTouched, false);
});


test("oversized allowlists are rejected before issuing a session token", async () => {
  const longDomains = Array.from({ length: 14 }, (_, index) =>
    "a".repeat(60) + String(index) + "." + "b".repeat(61) + "." + "c".repeat(61) + ".com"
  );
  await assert.rejects(
    () => signSessionToken(env, "browser-session-large", longDomains),
    /Combined allowedDomains length/
  );
});


test("Playwright fetch rejects private numeric hosts before launching a browser", async () => {
  let browserTouched = false;
  const mockEnv = {
    BROWSER: {
      async launch() { browserTouched = true; throw new Error("browser should not launch"); }
    }
  };
  await assert.rejects(
    () => callTool("browser_playwright_fetch", { url: "https://127.0.0.1/" }, mockEnv),
    /allowedDomains/
  );
  assert.equal(browserTouched, false);
});

test("Playwright fetch rejects non-HTTPS URLs before launching a browser", async () => {
  let browserTouched = false;
  const mockEnv = { BROWSER: { async launch() { browserTouched = true; } } };
  await assert.rejects(
    () => callTool("browser_playwright_fetch", { url: "http://example.com/" }, mockEnv),
    /Only public HTTPS/
  );
  assert.equal(browserTouched, false);
});


test("URL validation rejects localhost, internal suffixes, and private numeric hosts", () => {
  for (const value of [
    "https://localhost/",
    "https://service.internal/",
    "https://printer.local/",
    "https://127.0.0.1/",
    "https://169.254.169.254/"
  ]) {
    const host = new URL(value).hostname;
    assert.throws(() => validateUrl(value, [host]));
  }
});

test("Playwright fetch rejects redirects to a different hostname", async () => {
  let closed = false;
  const page = {
    async route() {},
    async goto() { return { status: () => 302 }; },
    url() { return "https://attacker.example/"; },
    async evaluate() { return { title: "", text: "" }; }
  };
  const browser = {
    async newPage() { return page; },
    async close() { closed = true; }
  };
  const mockEnv = { BROWSER: { async launch() { return browser; } } };
  await assert.rejects(
    () => callTool("browser_playwright_fetch", { url: "https://example.com/" }, mockEnv),
    /Final navigation left the exact permitted hostname/
  );
  assert.equal(closed, true);
});

test("Playwright fetch uses the injected Browser Run binding and closes the browser", async () => {
  let routeHandler;
  let closed = false;
  const page = {
    async route(pattern, handler) { assert.equal(pattern, "**/*"); routeHandler = handler; },
    async goto(url) { assert.equal(url, "https://example.com/"); return { status: () => 200 }; },
    url() { return "https://example.com/"; },
    async evaluate() { return { title: "Example Domain", text: "Example content" }; }
  };
  const browser = {
    async newPage() { return page; },
    async close() { closed = true; }
  };
  const mockEnv = { BROWSER: { async launch() { return browser; } } };
  const result = await callTool("browser_playwright_fetch", { url: "https://example.com/" }, mockEnv);
  assert.equal(result.isError, false);
  assert.match(result.content[0].text, /Example Domain/);
  assert.equal(closed, true);

  let aborted = false;
  await routeHandler({
    request() { return { url: () => "https://attacker.example/" }; },
    async abort() { aborted = true; },
    async continue() { throw new Error("cross-host request must not continue"); }
  });
  assert.equal(aborted, true);
});
