import { assertPublicExternalQuery } from "./public_query_safety.ts";

Deno.test("allows ordinary public bibliographic queries", () => {
  assertPublicExternalQuery("lithium-ion battery recycling review");
  assertPublicExternalQuery("grid-scale energy storage 2025 systematic review");
  assertPublicExternalQuery("API key management strategies in distributed systems");
});

Deno.test("blocks personal data and common credential formats", () => {
  const sensitiveQueries = [
    "research contact person@example.org",
    "-----BEGIN PRIVATE KEY-----",
    ["ghp_", "abcdefghijklmnopqrstuvwxyz123456"].join(""),
    ["github_pat_", "abcdefghijklmnopqrstuvwxyz123456"].join(""),
    ["sk-", "abcdefghijklmnopqrstuvwxyz123456"].join(""),
    ["sk_live_", "abcdefghijklmnop123456"].join(""),
    ["rk_test_", "abcdefghijklmnop123456"].join(""),
    ["AIza", "012345678901234567890123456789012345"].join(""),
    ["AKIA", "1234567890ABCDEF"].join(""),
    ["ASIA", "1234567890ABCDEF"].join(""),
    ["xoxb", "1234567890", "abcdefghijklmnop"].join("-"),
    ["glpat-", "abcdefghijklmnopqrstuvwxyz123456"].join(""),
    ["npm_", "abcdefghijklmnopqrstuvwxyz1234567890"].join(""),
    ["Bearer", "abcdefghijklmnopqrstuvwxyz0123456789"].join(" "),
    ["eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiIxMjM0NTY3ODkwIn0", "signaturevalue123456"].join("."),
    "password=not-a-real-password",
    "access_token: not-a-real-token"
  ];

  for (const query of sensitiveQueries) {
    let blocked = false;
    try {
      assertPublicExternalQuery(query);
    } catch (error) {
      blocked = error instanceof Error &&
        error.message === "query_blocked_by_external_data_safety_policy";
    }
    if (!blocked) throw new Error("Sensitive query was not blocked");
  }
});

Deno.test("uses one stable policy error for blocked inputs", () => {
  try {
    assertPublicExternalQuery("contact person@example.org");
  } catch (error) {
    if (error instanceof Error &&
      error.message === "query_blocked_by_external_data_safety_policy") return;
    throw error;
  }
  throw new Error("Expected sensitive query to be blocked");
});
