import { createClient } from "npm:@supabase/supabase-js@2.95.0";

const supabaseUrl = Deno.env.get("SUPABASE_URL");
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
if (!supabaseUrl || !serviceRoleKey) throw new Error("Missing Supabase runtime configuration");

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: { autoRefreshToken: false, persistSession: false },
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

async function apiKeyConfigured(): Promise<boolean> {
  const { data, error } = await supabase.rpc("flybrain_openrouter_secret", {
    p_name: "openrouter_api_key",
  });
  if (error) {
    console.error("Vault presence check failed", error.code ?? "unknown");
    return false;
  }
  return typeof data === "string" && data.length > 0;
}

Deno.serve(async (req: Request) => {
  if (req.method === "GET") {
    return json({
      service: "flybrain-openrouter-staging",
      status: "ok",
      model_route: "openrouter/free",
      api_key_configured: await apiKeyConfigured(),
      inference_enabled: false,
      note: "Inference is hard-disabled pending verified zero-spend enforcement and staging tests.",
    });
  }

  if (req.method === "POST") {
    return json({
      error: "inference_disabled",
      external_data_transfer: false,
      reason: "verified_zero_spend_enforcement_and_staging_tests_required",
    }, 503);
  }

  return json({ error: "method_not_allowed" }, 405);
});
