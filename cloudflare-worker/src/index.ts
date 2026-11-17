interface RateLimit {
  limit(options: { key: string }): Promise<{ success: boolean }>;
}

interface Env {
  FLYBRAIN_PUBLIC_LIMITER: RateLimit;
}

const REPOSITORY = "ramysaid721-sudo/FlyBrain-Research-Platform";
const BRANCH = "main";
const SOURCES = [
  "README.md",
  "components/FlyBrain-NOS/README.md",
  "components/URCAL/README.md"
];

type JsonRpc = { jsonrpc: "2.0"; id?: string | number | null; method: string; params?: any };

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" }
  });
}

function error(id: unknown, code: number, message: string): Response {
  return json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}

function terms(text: string): string[] {
  return [...new Set((text.toLowerCase().match(/[\p{L}\p{N}_-]{3,}/gu) ?? []))];
}

async function retrieve(question: string): Promise<Array<{source: string; relevance_score: number; excerpt: string}>> {
  const q = new Set(terms(question));
  const found: Array<{source: string; relevance_score: number; excerpt: string}> = [];
  await Promise.all(SOURCES.map(async (path) => {
    const url = `https://raw.githubusercontent.com/${REPOSITORY}/${BRANCH}/${path}`;
    try {
      const response = await fetch(url, { cf: { cacheTtl: 300, cacheEverything: true } });
      if (!response.ok) return;
      const body = await response.text();
      const paragraphs = body.split(/\n\s*\n/).map(x => x.replace(/\s+/g, " ").trim()).filter(x => x.length >= 45);
      for (const paragraph of paragraphs) {
        const p = new Set(terms(paragraph));
        let score = 0;
        for (const term of q) if (p.has(term)) score++;
        if (score) found.push({ source: path, relevance_score: score, excerpt: paragraph.slice(0, 1400) });
      }
    } catch { /* A source fetch failure must not break the whole request. */ }
  }));
  found.sort((a, b) => b.relevance_score - a.relevance_score || b.excerpt.length - a.excerpt.length);
  const unique = new Set<string>();
  return found.filter(item => {
    const key = item.source + item.excerpt.slice(0, 160);
    if (unique.has(key)) return false;
    unique.add(key);
    return true;
  }).slice(0, 6);
}

async function handleMcp(request: Request): Promise<Response> {
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (contentLength > 65536) return json({ error: "request_too_large" }, 413);
  if (!request.headers.get("content-type")?.toLowerCase().includes("application/json")) {
    return json({ error: "content_type_must_be_application_json" }, 415);
  }

  let rpc: JsonRpc;
  try { rpc = await request.json() as JsonRpc; } catch { return json({ error: "invalid_json" }, 400); }
  if (!rpc || rpc.jsonrpc !== "2.0" || typeof rpc.method !== "string") return json({ error: "invalid_json_rpc_request" }, 400);
  if (rpc.id === undefined && rpc.method.startsWith("notifications/")) return new Response(null, { status: 202 });
  if (rpc.method === "initialize") {
    const requested = rpc.params?.protocolVersion;
    const supported = ["2024-11-05", "2025-03-26", "2025-06-18"];
    const protocolVersion = supported.includes(requested) ? requested : "2025-03-26";
    return json({ jsonrpc: "2.0", id: rpc.id, result: {
      protocolVersion,
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "flybrain-research-bridge", version: "0.15.0" },
      instructions: "Use ask_flybrain to retrieve source-labelled FlyBrain-NOS and URCAL project context. Distinguish documented evidence from interpretation and hypotheses. The synthetic LIF runtime is not a biologically validated fly brain or standalone language model. This server is public and read-only."
    }});
  }
  if (rpc.method === "ping") return json({ jsonrpc: "2.0", id: rpc.id, result: {} });
  if (rpc.method === "tools/list") {
    return json({ jsonrpc: "2.0", id: rpc.id, result: { tools: [{
      name: "ask_flybrain",
      title: "Ask FlyBrain research system",
      description: "Public read-only retrieval of source-labelled FlyBrain-NOS and URCAL project evidence. ChatGPT synthesizes the returned excerpts; no paid model provider is required. This tool cannot write, edit, or delete project data.",
      inputSchema: { type: "object", properties: { question: { type: "string", minLength: 1, maxLength: 12000 } }, required: ["question"], additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: true }
    }] }});
  }
  if (rpc.method === "tools/call") {
    const name = rpc.params?.name;
    const question = rpc.params?.arguments?.question;
    if (name !== "ask_flybrain" || typeof question !== "string" || !question.trim() || question.length > 12000) return error(rpc.id, -32602, "Invalid tool or question");
    const research_context = await retrieve(question.trim());
    const result = {
      status: research_context.length ? "context_only" : "no_matching_context",
      answer_candidates: [],
      research_context,
      message: "No external language provider is configured. Use the returned project evidence as context and let the connected ChatGPT model synthesize the response.",
      scientific_scope: "The synthetic LIF runtime is not biologically validated and is not itself a natural-language answer generator.",
      external_data_transfer: false
    };
    return json({ jsonrpc: "2.0", id: rpc.id, result: {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result,
      isError: false
    }});
  }
  return error(rpc.id, -32601, "Method not found");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") return json({ status: "ok", service: "flybrain-cloudflare-worker", version: "0.15.0" });
    if (url.pathname !== "/mcp") return json({ error: "not_found" }, 404);
    if (request.method !== "POST") return new Response(null, { status: 405, headers: { allow: "POST" } });

    const clientKey = request.headers.get("cf-connecting-ip") ?? "anonymous";
    const { success } = await env.FLYBRAIN_PUBLIC_LIMITER.limit({ key: clientKey });
    if (!success) return json({ error: "rate_limit_exceeded", retry_after_seconds: 60 }, 429);
    return handleMcp(request);
  }
};