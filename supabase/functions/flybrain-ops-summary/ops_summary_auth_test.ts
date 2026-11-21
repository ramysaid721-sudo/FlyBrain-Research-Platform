import {
  isOriginAllowed,
  isOwnerAllowed,
  parseOwnerAllowlist,
} from "./ops_summary_auth.ts";

Deno.test("owner allowlist accepts only exact UUID members", () => {
  const owner = "123e4567-e89b-42d3-a456-426614174000";
  const other = "123e4567-e89b-42d3-a456-426614174001";
  const allowlist = parseOwnerAllowlist(owner);
  if (!isOwnerAllowed(owner, allowlist)) throw new Error("owner should pass");
  if (isOwnerAllowed(other, allowlist)) throw new Error("non-owner must fail");
  if (isOwnerAllowed("not-a-uuid", allowlist)) throw new Error("malformed ID must fail");
});

Deno.test("missing or malformed allowlist fails closed", () => {
  if (parseOwnerAllowlist("")) throw new Error("empty allowlist must be null");
  let rejected = false;
  try { parseOwnerAllowlist("owner@example.com"); } catch { rejected = true; }
  if (!rejected) throw new Error("malformed allowlist must throw");
  if (isOwnerAllowed("123e4567-e89b-42d3-a456-426614174000", null)) {
    throw new Error("missing allowlist must deny access");
  }
});

Deno.test("origin policy permits only the configured HTTPS origin", () => {
  if (!isOriginAllowed("https://flybrain.example", "https://flybrain.example")) {
    throw new Error("configured origin should pass");
  }
  if (isOriginAllowed("https://attacker.example", "https://flybrain.example")) {
    throw new Error("foreign origin must fail");
  }
  if (isOriginAllowed("http://flybrain.example", "http://flybrain.example")) {
    throw new Error("non-HTTPS origin must fail");
  }
  if (isOriginAllowed("https://flybrain.example.evil", "https://flybrain.example")) {
    throw new Error("origin suffix attack must fail");
  }
  if (!isOriginAllowed(null, "https://flybrain.example")) {
    throw new Error("non-browser caller should still reach JWT auth");
  }
});
