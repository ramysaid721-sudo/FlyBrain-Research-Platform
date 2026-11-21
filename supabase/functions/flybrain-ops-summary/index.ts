import { withSupabase } from "npm:@supabase/server@1";
import {
  isOriginAllowed,
  isOwnerAllowed,
  parseOwnerAllowlist,
} from "./ops_summary_auth.ts";

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store, max-age=0",
  "pragma": "no-cache",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
};

function response(
  body: Record<string, unknown>,
  status: number,
  origin: string | null,
  allowedOrigin: string | null,
): Response {
  const headers = new Headers(JSON_HEADERS);
  if (origin && allowedOrigin && isOriginAllowed(origin, allowedOrigin)) {
    headers.set("access-control-allow-origin", allowedOrigin);
    headers.set("vary", "Origin");
    headers.set("access-control-allow-headers", "authorization, apikey, content-type, x-client-info");
    headers.set("access-control-allow-methods", "GET, OPTIONS");
  }
  return new Response(JSON.stringify(body), { status, headers });
}

const authenticatedHandler = withSupabase(
  { auth: "user" },
  async (req, ctx) => {
    const origin = req.headers.get("origin");
    const allowedOrigin = Deno.env.get("FLYBRAIN_OPS_DASHBOARD_ORIGIN");
    if (!isOriginAllowed(origin, allowedOrigin)) {
      return response({ error: "origin_not_allowed" }, 403, origin, allowedOrigin);
    }

    if (req.method !== "GET") {
      return response({ error: "method_not_allowed" }, 405, origin, allowedOrigin);
    }

    let allowlist: Set<string> | null;
    try {
      allowlist = parseOwnerAllowlist(Deno.env.get("FLYBRAIN_OPS_OWNER_IDS"));
    } catch {
      return response({ error: "ops_auth_configuration_invalid" }, 503, origin, allowedOrigin);
    }
    if (!allowlist) {
      return response({ error: "ops_auth_not_configured" }, 503, origin, allowedOrigin);
    }

    const userId = ctx.userClaims?.id ?? ctx.jwtClaims?.sub;
    if (!isOwnerAllowed(userId, allowlist)) {
      return response({ error: "forbidden" }, 403, origin, allowedOrigin);
    }

    const { data, error } = await ctx.supabaseAdmin.rpc("flybrain_ops_summary");
    if (error || !data || typeof data !== "object" || Array.isArray(data)) {
      // Do not forward database errors, SQL, or internal schema details.
      return response({ error: "ops_summary_unavailable" }, 503, origin, allowedOrigin);
    }

    return response(data as Record<string, unknown>, 200, origin, allowedOrigin);
  },
);

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("origin");
  const allowedOrigin = Deno.env.get("FLYBRAIN_OPS_DASHBOARD_ORIGIN");
  if (req.method === "OPTIONS") {
    if (!isOriginAllowed(origin, allowedOrigin)) {
      return response({ error: "origin_not_allowed" }, 403, origin, allowedOrigin);
    }
    if (!origin || !allowedOrigin) {
      return response({ error: "cors_not_configured" }, 503, origin, allowedOrigin);
    }
    return new Response(null, {
      status: 204,
      headers: {
        ...JSON_HEADERS,
        "access-control-allow-origin": allowedOrigin,
        "access-control-allow-methods": "GET, OPTIONS",
        "access-control-allow-headers": "authorization, apikey, content-type, x-client-info",
        "access-control-max-age": "300",
        "vary": "Origin",
      },
    });
  }
  return await authenticatedHandler(req);
});
