import test from "node:test";
import assert from "node:assert/strict";
import { callTool, readSessionToken, signSessionToken, validateUrl } from "./index.js";

const env = { FLYBRAIN_SESSION_SIGNING_KEY: "test-session-signing-key-".padEnd(40, "x") };

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

test("HTTP URLs are rejected for browser sessions", () => {
  assert.throws(() => validateUrl("http://example.com/", ["example.com"]), /HTTPS/);
});

test("click, type, and keypress require explicit approval before browser access", async () => {
  let browserTouched = false;
  const mockEnv = {
    ...env,
    BROWSER: {
      getSession() { browserTouched = true; throw new Error("browser must not be touched without approval"); },
      connectSession() { browserTouched = true; throw new Error("browser must not be touched without approval"); }
    }
  };
  const sessionId = await signSessionToken(mockEnv, "approval-session", ["example.com"]);
  const calls = [
    ["browser_session_click", { sessionId, selector: "button" }],
    ["browser_session_type", { sessionId, selector: "input", text: "hello" }],
    ["browser_session_press", { sessionId, key: "ENTER" }]
  ];
  for (const [name, args] of calls) {
    const result = await callTool(name, args, mockEnv);
    assert.equal(result.isError, false);
    assert.equal(JSON.parse(result.content[0].text).status, "approval_required");
  }
  assert.equal(browserTouched, false);
});

test("invalid side-effect approval types are rejected", async () => {
  const sessionId = await signSessionToken(env, "approval-session", ["example.com"]);
  await assert.rejects(() => callTool("browser_session_click", {
    sessionId, selector: "button", allowSideEffects: "yes"
  }, env), /allowSideEffects must be boolean/);
});
