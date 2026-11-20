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
