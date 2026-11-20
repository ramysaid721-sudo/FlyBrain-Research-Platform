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

Deno.serve((req: Request) => {
  if (req.method === "GET") {
    return json({
      service: "flybrain-openrouter-staging",
      status: "ok",
      model_route: "openrouter/free",
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
