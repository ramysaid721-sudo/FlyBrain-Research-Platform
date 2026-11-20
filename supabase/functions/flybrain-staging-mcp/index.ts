import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { unzipSync } from "npm:fflate@0.8.2";

const REPOSITORY = "ramysaid721-sudo/FlyBrain-Research-Platform";
const BRANCH = "592ec1d36f1f97ef7c49598f3028f3dd87aac90c";
const SOURCES = [
  "README.md",
  "CHATGPT_PLUGIN_SETUP.md",
  "CHATGPT_ACTION_SETUP.md",
  "VERCEL_DEPLOYMENT.md",
  "automation/README.md",
  "reports/VALIDATION_2026-11-17.md",
  "reports/CHATGPT_BRIDGE_VALIDATION_2026-11-17.md",
  "docs/MULTI_AGENT_ORCHESTRATION_PLAN.md",
  "bridge/mcp_server.py",
  "bridge/chat_api.py",
  "bridge/tool_manager.py",
  "bridge/browser_use_adapter.py",
  "bridge/test_mcp_server.py",
  "bridge/test_browser_use_adapter.py",
  "cloudflare-staging/worker/index.ts",
  "cloudflare-staging/README_AR.md",
  "cloudflare-worker/src/index.ts",
  "cloudflare-worker/README.md",
  "cloudflare-worker/tests/worker.spec.ts",
  ".github/workflows/ci.yml",
  ".github/workflows/deploy-flybrain-staging.yml",
];
const ARCHIVE_PATH = "FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip";
const ARCHIVE_GIT_BLOB_SHA1 = "b02b9f10fb411bbcfd45418cfb51b9a548cc74a2";
let archiveCache: Promise<Array<{source:string;body:string}>> | null = null;
let archiveSourceCount = 0;
let archiveLoadError: string | null = null;
async function loadArchiveSources(): Promise<Array<{source:string;body:string}>> {
  if (!archiveCache) {
    archiveCache = (async () => {
      const url = `https://raw.githubusercontent.com/${REPOSITORY}/${BRANCH}/${ARCHIVE_PATH}`;
      const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error(`release archive fetch failed: HTTP ${response.status}`);
      const declared = Number(response.headers.get("content-length") ?? "0");
      if (declared > 2_000_000) throw new Error("release archive exceeds compressed-size limit");
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.byteLength > 2_000_000) throw new Error("release archive exceeds compressed-size limit");
      const prefix = new TextEncoder().encode("blob " + bytes.byteLength + String.fromCharCode(0));
      const gitBlob = new Uint8Array(prefix.length + bytes.length);
      gitBlob.set(prefix); gitBlob.set(bytes, prefix.length);
      const digest = await crypto.subtle.digest("SHA-1", gitBlob);
      const actualSha = Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2,"0")).join("");
      if (actualSha !== ARCHIVE_GIT_BLOB_SHA1) throw new Error("release archive integrity check failed");
      const files = unzipSync(bytes);
      const names = Object.keys(files);
      if (names.length > 140) throw new Error("release archive entry-count limit exceeded");
      const allowed = /\.(md|py|ya?ml|json|toml|txt)$/i;
      const root = "FlyBrain_Research_Platform_v0.14.0/";
      const docs: Array<{source:string;body:string}> = [];
      let total = 0;
      for (const name of names) {
        if (!name.startsWith(root) || name.endsWith("/") || !allowed.test(name)) continue;
        const data = files[name];
        if (data.byteLength > 131072) continue;
        total += data.byteLength;
        if (total > 1_500_000) throw new Error("release archive expanded-size limit exceeded");
        try {
          const body = new TextDecoder("utf-8", {fatal:true}).decode(data);
          if (body.includes(String.fromCharCode(0))) continue;
          docs.push({source: "release-archive/" + name.slice(root.length), body});
        } catch { /* skip non-UTF-8 entries */ }
      }
      if (!docs.length) throw new Error("release archive contained no eligible text sources");
      archiveSourceCount = docs.length;
      archiveLoadError = null;
      return docs;
    })().catch(error => {
      archiveCache = null;
      archiveSourceCount = 0;
      archiveLoadError = error instanceof Error ? error.message : "archive load failed";
      throw error;
    });
  }
  return await archiveCache;
}
const HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "content-type, accept, mcp-session-id, last-event-id, authorization, apikey",
};
function json(data: unknown, status = 200, extra: Record<string,string> = {}) {
  return new Response(JSON.stringify(data), { status, headers: { ...HEADERS, ...extra } });
}
function rpcError(id: unknown, code: number, message: string) {
  return json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}
function terms(value: string) {
  return [...new Set(value.toLowerCase().match(/[\p{L}\p{N}_-]{3,}/gu) ?? [])];
}
async function retrieve(question: string) {
  const queryTerms = new Set(terms(question));
  const documents: Array<{source:string;body:string}> = [];
  await Promise.all(SOURCES.map(async (path) => {
    const url = `https://raw.githubusercontent.com/${REPOSITORY}/${BRANCH}/${path}`;
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
      if (!response.ok) return;
      documents.push({source:path,body:await response.text()});
    } catch { /* a missing or unavailable source is skipped */ }
  }));
  try { documents.push(...await loadArchiveSources()); } catch { /* retain the existing pinned source corpus */ }
  const found: Array<{source:string; relevance_score:number; excerpt:string}> = [];
  for (const document of documents) {
    const paragraphs = document.body.split(/\n\s*\n/).map(p => p.replace(/\s+/g, " ").trim()).filter(p => p.length >= 45);
    for (const paragraph of paragraphs) {
      const paragraphTerms = new Set(terms(paragraph));
      let score = 0;
      for (const term of queryTerms) if (paragraphTerms.has(term)) score++;
      if (score > 0) found.push({ source: document.source, relevance_score: score, excerpt: paragraph.slice(0, 1400) });
    }
  }
  found.sort((a,b) => b.relevance_score - a.relevance_score || b.excerpt.length - a.excerpt.length);
  const seen = new Set<string>();
  return found.filter(item => {
    const key = item.source + item.excerpt.slice(0,160);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0,6);
}



const PUBLIC_QUERY_SENSITIVE_PATTERNS = [
  /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
  /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/,
  /\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/,
  /\bsk-[A-Za-z0-9_-]{20,}\b/,
  /(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*\S+/i
];
function assertPublicExternalQuery(query: string) {
  if (PUBLIC_QUERY_SENSITIVE_PATTERNS.some(pattern => pattern.test(query))) {
    throw new Error("query_blocked_by_external_data_safety_policy");
  }
}

async function researchSearch(args: any) {
  if (!args || typeof args !== "object" || Array.isArray(args) ||
      Object.keys(args).some(k => !["query","page_size"].includes(k)) ||
      typeof args.query !== "string" || !args.query.trim() || args.query.length > 400) {
    throw new Error("research_search requires a query (max 400 characters) and optional page_size");
  }
  const pageSize = args.page_size ?? 5;
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 10) throw new Error("page_size must be an integer from 1 to 10");
  const query = args.query.trim();
  assertPublicExternalQuery(query);
  const params = new URLSearchParams({ "query.bibliographic": query, rows: String(pageSize) });
  const response = await fetch(`https://api.crossref.org/works?${params.toString()}`, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(8000),
    redirect: "error",
  });
  if (!response.ok) throw new Error(`Crossref returned HTTP ${response.status}`);
  let payload: any;
  try {
    payload = await response.json();
  } catch {
    throw new Error("crossref_invalid_json");
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload) ||
      payload.status !== "ok" || !payload.message || typeof payload.message !== "object" ||
      Array.isArray(payload.message) || !Array.isArray(payload.message.items) ||
      !Number.isFinite(payload.message["total-results"]) || payload.message["total-results"] < 0 ||
      payload.message.items.some((item: any) => !item || typeof item !== "object" || Array.isArray(item))) {
    throw new Error("crossref_invalid_response");
  }
  const message = payload.message;
  const results = message.items.slice(0,pageSize).map((item: any) => {
    const dateParts = item["published-print"]?.["date-parts"]?.[0] ??
      item["published-online"]?.["date-parts"]?.[0] ??
      item.published?.["date-parts"]?.[0] ?? [];
    const year = Array.isArray(dateParts) && Number.isFinite(dateParts[0]) ? dateParts[0] : null;
    const authors = Array.isArray(item.author)
      ? item.author.slice(0,8)
          .filter((a: any) => a && typeof a === "object" && !Array.isArray(a))
          .map((a: any) => [a.given, a.family].filter((v: any) => typeof v === "string" && v.trim()).join(" "))
          .filter(Boolean).join(", ")
      : "";
    return {
      title: Array.isArray(item.title) && typeof item.title[0] === "string" ? item.title[0] : "",
      authors,
      journal: Array.isArray(item["container-title"]) && typeof item["container-title"][0] === "string" ? item["container-title"][0] : "",
      year,
      doi: typeof item.DOI === "string" ? item.DOI : null,
      type: typeof item.type === "string" ? item.type : null,
      score: typeof item.score === "number" && Number.isFinite(item.score) ? item.score : null,
      abstract: typeof item.abstract === "string" ? item.abstract.replace(/<[^>]*>/g," ").replace(/\s+/g," ").trim().slice(0,1600) : "",
      url: typeof item.URL === "string" ? item.URL : (typeof item.DOI === "string" ? `https://doi.org/${item.DOI}` : null),
    };
  });
  return { status: "completed", provider: "Crossref", query, hit_count: message["total-results"], returned: results.length, results };
}

const POLICY_VERSION = "1.0.0";
const DEFAULT_ALLOWLIST: Record<string,{purpose:string;risk:string}> = {
  "pip-audit": { purpose: "dependency vulnerability auditing", risk: "low" },
  "bandit": { purpose: "Python static security analysis", risk: "low" },
  "ruff": { purpose: "Python linting and static checks", risk: "low" },
  "pytest": { purpose: "automated tests", risk: "low" }
};
const DENIED_NAMES = new Set(["curl","wget","nc","netcat","nmap","masscan","metasploit","sqlmap","hydra","john","hashcat","proxychains","tor"]);
function normalizeToolName(name: unknown): string {
  if (typeof name !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(name.trim())) throw new Error("Invalid package/tool name");
  return name.trim().replace(/[-_.]+/g,"-").toLowerCase();
}
async function callServiceRpc(name: string, args: Record<string, unknown>) {
  const base = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!base || !key) throw new Error("service_configuration_missing");
  const response = await fetch(`${base}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: { "content-type": "application/json", apikey: key, authorization: `Bearer ${key}` },
    body: JSON.stringify(args),
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error("task_backend_unavailable");
  return await response.json();
}
async function createCapabilityToken(): Promise<{token:string;hash:string}> {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  const token = btoa(binary).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");
  const digest = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(token));
  const hash = Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,"0")).join("");
  return {token,hash};
}
async function hashPresentedCapabilityToken(token: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(token));
  return Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,"0")).join("");
}
function validCapabilityToken(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]{43}$/.test(value);
}

function validateTaskSubmit(args: any) {
  if (!args || typeof args !== "object" || Array.isArray(args) ||
      Object.keys(args).some(k => !["query","page_size","idempotency_key","data_classification"].includes(k)) ||
      typeof args.query !== "string" || !args.query.trim() || args.query.length > 400 ||
      args.data_classification !== "public") {
    throw new Error("task_submit requires a query, data_classification=public, optional page_size and idempotency_key");
  }
  const query = args.query.trim();
  assertPublicExternalQuery(query);
  const pageSize = args.page_size ?? 5;
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 10) throw new Error("page_size must be 1 to 10");
  const idempotency = args.idempotency_key ?? null;
  if (idempotency !== null && (typeof idempotency !== "string" || idempotency.length < 8 || idempotency.length > 120 || !/^[A-Za-z0-9._:-]+$/.test(idempotency))) throw new Error("invalid_idempotency_key");
  return { query, page_size: pageSize, idempotency_key: idempotency };
}

function validateTaskGroup(args: any) {
  if (!args || typeof args !== "object" || Array.isArray(args) ||
      Object.keys(args).some(k => !["tasks","idempotency_key","data_classification"].includes(k)) ||
      args.data_classification !== "public" ||
      !Array.isArray(args.tasks) || args.tasks.length < 1 || args.tasks.length > 10 ||
      typeof args.idempotency_key !== "string" ||
      args.idempotency_key.length < 8 || args.idempotency_key.length > 100 ||
      !/^[A-Za-z0-9._:-]+$/.test(args.idempotency_key)) {
    throw new Error("task_group_submit requires 1-10 tasks, data_classification=public, and a valid idempotency_key");
  }
  const tasks = args.tasks.map((task: any) => {
    if (!task || typeof task !== "object" || Array.isArray(task) ||
        Object.keys(task).some(k => !["query","page_size"].includes(k))) {
      throw new Error("each task must contain only query and optional page_size");
    }
    const validated = validateTaskSubmit({
      query: task.query,
      page_size: task.page_size,
      data_classification: "public"
    });
    return { query: validated.query, page_size: validated.page_size };
  });
  return { tasks, idempotency_key: args.idempotency_key };
}

function toolManagerStatus() {
  return {
    status: "ready",
    component: "FlyBrain Tool Lifecycle Manager",
    policy_version: POLICY_VERSION,
    runtime: "Supabase Deno Edge Function",
    mode: "policy-and-inventory-only",
    installed_python_packages: null,
    python_package_inventory: "not_available_in_deno_runtime",
    automatic_installation: false,
    automatic_updates: false,
    isolated_worker_ready: false,
    task_worker_ready: true,
    durable_queue_ready: true,
    task_group_orchestration_ready: true,
    max_tasks_per_group: 10,
    supported_async_task_types: ["research_search"],
    reason: "A restricted staging task worker and durable queue support individual and grouped Crossref research-search jobs. Group status aggregates child states and bounded public bibliographic results. Package installation and shell execution remain disabled.",
    security: { fail_closed: true, no_shell_execution: true, no_runtime_package_install: true, no_secrets_exposed: true, least_privilege: true }
  };
}
function toolCatalog() {
  return {
    status: "completed",
    policy_version: POLICY_VERSION,
    approved_low_risk_candidates: Object.entries(DEFAULT_ALLOWLIST).sort(([a],[b])=>a.localeCompare(b)).map(([name,meta])=>({name,...meta,installation:"requires isolated worker"})),
    blocked_high_impact_examples: [...DENIED_NAMES].sort(),
    note: "Catalog entries are policy candidates, not installed tools."
  };
}
function assessTool(args: any) {
  if (!args || typeof args !== "object" || Array.isArray(args) || Object.keys(args).some(k=>!["name","version","source"].includes(k)) || !("name" in args)) throw new Error("assess_tool requires name and accepts only version/source");
  const name = normalizeToolName(args.name);
  const version = args.version ?? "";
  const source = args.source ?? "";
  if (typeof version !== "string" || (version && (version.length > 80 || !/^[A-Za-z0-9.*+!_-]+$/.test(version)))) throw new Error("Invalid version constraint");
  if (typeof source !== "string" || source.length > 300) throw new Error("Invalid source descriptor");
  if (DENIED_NAMES.has(name)) return {status:"blocked",name,reason:"This high-impact tool is not eligible for automatic installation.",requires_human_security_review:true};
  if (!(name in DEFAULT_ALLOWLIST)) return {status:"review_required",name,reason:"Tool is not in the narrowly scoped low-risk allowlist.",requires_human_security_review:true,installation_authorized:false};
  return {
    status:"eligible_for_isolated_testing",name,
    version_constraint:version||"latest-not-pinned",
    source:source||"package index must be verified by worker",
    purpose:DEFAULT_ALLOWLIST[name].purpose,
    installation_authorized:false,
    next_step:"An isolated worker must verify provenance, hashes, licenses, dependencies, run tests, and produce a signed artifact before activation."
  };
}

async function checkGlobalRateLimit(ip: string): Promise<"allowed" | "limited" | "unavailable"> {
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) return "unavailable";
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ip));
  const keyHash = Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("");
  try {
    const response = await fetch(`${supabaseUrl}/rest/v1/rpc/consume_flybrain_rate_limit`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "apikey": serviceRoleKey,
        "authorization": `Bearer ${serviceRoleKey}`,
      },
      body: JSON.stringify({ p_key_hash: keyHash, p_limit: 30, p_window_seconds: 60 }),
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return "unavailable";
    const allowed = await response.json();
    return allowed === true ? "allowed" : "limited";
  } catch {
    return "unavailable";
  }
}


async function readBodyLimited(request: Request, maxBytes: number): Promise<{text:string;tooLarge:boolean}> {
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > maxBytes) return {text:"",tooLarge:true};
  const reader = request.body?.getReader();
  if (!reader) return {text:"",tooLarge:false};
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      total += part.value.byteLength;
      if (total > maxBytes) {
        try { await reader.cancel(); } catch { /* cancellation is best-effort */ }
        return {text:"",tooLarge:true};
      }
      chunks.push(part.value);
    }
  } finally {
    try { reader.releaseLock(); } catch { /* already released */ }
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return {text:new TextDecoder("utf-8",{fatal:true}).decode(bytes),tooLarge:false};
}

Deno.serve(async (request: Request) => {
  const url = new URL(request.url);
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: HEADERS });
  if (url.pathname.endsWith("/health") && request.method === "GET") {
    const configured = Boolean(Deno.env.get("SUPABASE_URL") && Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"));
    return json({
      status: configured ? "ok" : "degraded",
      service: "flybrain-supabase-edge-staging",
      version: "0.20.5-staging",
      mode: "restricted_staging",
      async_task_queue: "enabled",
      task_worker: "enabled",
      rate_limiter: configured ? "database_atomic_global" : "not_configured",
      source_repository: REPOSITORY,
      public_web_search: false,
      research_literature_search: true,
      interactive_browser: false,
      tool_policy_assessment: true,
    }, configured ? 200 : 503);
  }
  if (request.method !== "POST") return new Response(null, { status: 405, headers: { ...HEADERS, allow: "GET, POST, OPTIONS" } });
  if (!(request.headers.get("content-type") ?? "").toLowerCase().includes("application/json")) return json({ error: "content_type_must_be_application_json" }, 415);
  let rawBody: string;
  try {
    const body = await readBodyLimited(request,65536);
    if (body.tooLarge) return json({ error: "request_too_large" }, 413);
    rawBody = body.text;
  } catch { return json({ error: "invalid_request_body" }, 400); }
  if (!rawBody.length) return rpcError(null,-32600,"Empty request body");
  let rpc: any;
  try { rpc = JSON.parse(rawBody); } catch { return rpcError(null, -32700, "Parse error"); }
  if (!rpc || rpc.jsonrpc !== "2.0" || typeof rpc.method !== "string") return rpcError(rpc?.id, -32600, "Invalid Request");
  const realIp = request.headers.get("x-real-ip")?.trim();
  const forwardedChain = (request.headers.get("x-forwarded-for") ?? "").split(",").map(v => v.trim()).filter(Boolean);
  const ip = request.headers.get("cf-connecting-ip")?.trim() || realIp || forwardedChain.at(-1) || "anonymous";
  const limitState = await checkGlobalRateLimit(ip);
  if (limitState === "unavailable") return json({ error: "rate_limit_backend_unavailable", message: "The shared rate limiter is unavailable; request rejected safely." }, 503);
  if (limitState === "limited") return json({ error: "rate_limit_exceeded", retry_after_seconds: 60 }, 429, { "retry-after": "60" });
  if (rpc.id === undefined && rpc.method.startsWith("notifications/")) return new Response(null, { status: 202, headers: HEADERS });

  if (rpc.method === "initialize") {
    const requested = rpc.params?.protocolVersion;
    const supported = ["2024-11-05", "2025-03-26", "2025-06-18"];
    return json({ jsonrpc: "2.0", id: rpc.id, result: {
      protocolVersion: supported.includes(requested) ? requested : "2025-03-26",
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "flybrain-research-bridge", version: "0.20.5-staging" },
      instructions: "Use ask_flybrain for source-labelled FlyBrain-NOS and URCAL project evidence. Distinguish documented evidence from inference and hypotheses. This server provides read-only project retrieval, literature search, and restricted asynchronous Crossref tasks that can be submitted individually or in groups of up to ten. Task and group status require the one-time capability_token returned at submission; UUIDs alone do not grant access. Store that token securely because it cannot be recovered. The token is not returned again for an idempotent duplicate submission. It does not write project files, execute arbitrary code, install packages, or provide interactive browser automation."
    }});
  }
  if (rpc.method === "ping") return json({ jsonrpc: "2.0", id: rpc.id, result: {} });
  if (rpc.method === "tools/list") return json({ jsonrpc: "2.0", id: rpc.id, result: { tools: [
    {
      name: "ask_flybrain",
      title: "Ask FlyBrain research system",
      description: "Public read-only retrieval of source-labelled FlyBrain-NOS and URCAL project evidence from a pinned repository revision. ChatGPT synthesizes returned excerpts. This tool cannot write, edit, or delete project data.",
      inputSchema: { type: "object", properties: { question: { type: "string", minLength: 1, maxLength: 12000 } }, required: ["question"], additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: true }
    },
    {
      name: "research_search",
      title: "Scientific literature search",
      description: "Search public scholarly literature metadata through the public Crossref API. The query is sent to Crossref. Submit only public bibliographic search terms; do not submit unpublished research, private data, personal data, credentials, or secrets. Known email and credential patterns are blocked. This is not general web search.",
      inputSchema: { type: "object", properties: { query: { type: "string", minLength: 1, maxLength: 400 }, page_size: { type: "integer", minimum: 1, maximum: 10, default: 5 } }, required: ["query"], additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: true }
    },
    {
      name: "browser_use_status",
      title: "Interactive browser readiness",
      description: "Report the current staging browser automation boundary. This tool does not launch a browser.",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: false }
    },
    {
      name: "tool_manager_status",
      title: "Tool lifecycle manager status",
      description: "Report tool policy mode, security controls, and isolated worker readiness. Does not install or execute packages.",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: false }
    },
    {
      name: "tool_catalog",
      title: "Approved tool candidates",
      description: "List narrowly allowlisted low-risk tool candidates and blocked high-impact examples. Does not install tools.",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: false }
    },
    {
      name: "task_submit",
      title: "Submit asynchronous research task",
      description: "Queue a durable Crossref literature-search job for background processing. Requires data_classification=public. The query is stored in the staging task ledger and sent to Crossref when processed. Do not submit private or unpublished research, personal data, credentials, or secrets. Only research_search is supported; no code execution or package installation is available.",
      inputSchema: { type: "object", properties: {
        query: { type: "string", minLength: 1, maxLength: 400 },
        page_size: { type: "integer", minimum: 1, maximum: 10, default: 5 },
        data_classification: { type: "string", enum: ["public"] },
        idempotency_key: { type: "string", minLength: 8, maxLength: 120 }
      }, required: ["query","data_classification"], additionalProperties: false },
      annotations: { readOnlyHint: false, openWorldHint: true }
    },
    {
      name: "task_status",
      title: "Check asynchronous task status",
      description: "Retrieve task status only with task_id and the one-time capability_token returned by task_submit. UUID alone is not authorization.",
      inputSchema: { type: "object", properties: { task_id: { type: "string", format: "uuid" }, capability_token: { type: "string", minLength: 43, maxLength: 43 } }, required: ["task_id","capability_token"], additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: false }
    },
    {
      name: "task_group_submit",
      title: "Submit a group of asynchronous research tasks",
      description: "Atomically queue 1-10 independent public Crossref literature searches as one tracked group. Requires data_classification=public and a group idempotency_key. Each child task is processed independently by the restricted Crossref worker. Do not submit private or unpublished research, personal data, credentials, or secrets.",
      inputSchema: { type: "object", properties: {
        tasks: { type: "array", minItems: 1, maxItems: 10, items: { type: "object", properties: {
          query: { type: "string", minLength: 1, maxLength: 400 },
          page_size: { type: "integer", minimum: 1, maximum: 10, default: 5 }
        }, required: ["query"], additionalProperties: false } },
        data_classification: { type: "string", enum: ["public"] },
        idempotency_key: { type: "string", minLength: 8, maxLength: 100 }
      }, required: ["tasks","data_classification","idempotency_key"], additionalProperties: false },
      annotations: { readOnlyHint: false, openWorldHint: true }
    },
    {
      name: "task_group_status",
      title: "Check asynchronous research task group",
      description: "Retrieve group status and child results only with group_id and the one-time capability_token returned by task_group_submit. UUID alone is not authorization.",
      inputSchema: { type: "object", properties: { group_id: { type: "string", format: "uuid" }, capability_token: { type: "string", minLength: 43, maxLength: 43 } }, required: ["group_id","capability_token"], additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: false }
    },
    {
      name: "assess_tool",
      title: "Assess a tool candidate",
      description: "Apply the fail-closed FlyBrain policy to a candidate package. Assessment never installs or executes the candidate.",
      inputSchema: { type: "object", properties: {
        name: { type: "string", minLength: 1, maxLength: 100 },
        version: { type: "string", maxLength: 80 },
        source: { type: "string", maxLength: 300 }
      }, required: ["name"], additionalProperties: false },
      annotations: { readOnlyHint: true, openWorldHint: false }
    }
  ] }});
  if (rpc.method === "tools/call") {
    const name = rpc.params?.name;
    const args = rpc.params?.arguments ?? {};
    if (name === "tool_manager_status" || name === "tool_catalog") {
      if (Object.keys(args).length) return rpcError(rpc.id, -32602, name + " accepts no arguments");
      const data = name === "tool_manager_status" ? toolManagerStatus() : toolCatalog();
      return json({ jsonrpc:"2.0", id:rpc.id, result:{content:[{type:"text",text:JSON.stringify(data)}],structuredContent:data,isError:false} });
    }
    if (name === "task_submit") {
      try {
        const input = validateTaskSubmit(args);
        const capability = await createCapabilityToken();
        const data = await callServiceRpc("flybrain_enqueue_task", {
          p_task_type: "research_search",
          p_payload: { query: input.query, page_size: input.page_size },
          p_idempotency_key: input.idempotency_key,
          p_access_token_hash: capability.hash
        });
        const response = data && data.duplicate === false
          ? { ...data, capability_token: capability.token, capability_token_once: true }
          : { ...data, capability_token_issued: false, capability_token_note: "This idempotent request already exists. The original capability token is not recoverable; submit with a new idempotency_key to create a new task and token." };
        return json({ jsonrpc:"2.0", id:rpc.id, result:{content:[{type:"text",text:JSON.stringify(response)}],structuredContent:response,isError:false} });
      } catch (error) {
        return rpcError(rpc.id,-32602,error instanceof Error ? error.message : "Task submission failed");
      }
    }
    if (name === "task_status") {
      if (!args || typeof args !== "object" || Array.isArray(args) ||
          Object.keys(args).length !== 2 || typeof args.task_id !== "string" ||
          !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(args.task_id) ||
          !validCapabilityToken(args.capability_token)) {
        return rpcError(rpc.id,-32602,"task_status requires task_id and its 43-character capability_token");
      }
      try {
        const tokenHash = await hashPresentedCapabilityToken(args.capability_token);
        const data = await callServiceRpc("flybrain_task_status",{p_task_id:args.task_id,p_access_token_hash:tokenHash});
        if (data === null) return rpcError(rpc.id,-32004,"Task not found or capability token invalid");
        return json({jsonrpc:"2.0",id:rpc.id,result:{content:[{type:"text",text:JSON.stringify(data)}],structuredContent:data,isError:false}});
      } catch {
        return rpcError(rpc.id,-32000,"Task status service unavailable");
      }
    }
    if (name === "task_group_submit") {
      try {
        const input = validateTaskGroup(args);
        const capability = await createCapabilityToken();
        const data = await callServiceRpc("flybrain_enqueue_task_group", {
          p_tasks: input.tasks,
          p_idempotency_key: input.idempotency_key,
          p_data_classification: "public",
          p_access_token_hash: capability.hash
        });
        const response = data && data.duplicate === false
          ? { ...data, capability_token: capability.token, capability_token_once: true }
          : { ...data, capability_token_issued: false, capability_token_note: "This idempotent group already exists. The original capability token is not recoverable; submit with a new idempotency_key to create a new group and token." };
        return json({jsonrpc:"2.0",id:rpc.id,result:{content:[{type:"text",text:JSON.stringify(response)}],structuredContent:response,isError:false}});
      } catch (error) {
        return rpcError(rpc.id,-32602,error instanceof Error ? error.message : "Task group submission failed");
      }
    }
    if (name === "task_group_status") {
      if (!args || typeof args !== "object" || Array.isArray(args) ||
          Object.keys(args).length !== 2 || typeof args.group_id !== "string" ||
          !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(args.group_id) ||
          !validCapabilityToken(args.capability_token)) {
        return rpcError(rpc.id,-32602,"task_group_status requires group_id and its 43-character capability_token");
      }
      try {
        const tokenHash = await hashPresentedCapabilityToken(args.capability_token);
        const data = await callServiceRpc("flybrain_task_group_status",{p_group_id:args.group_id,p_access_token_hash:tokenHash});
        if (data === null) return rpcError(rpc.id,-32004,"Task group not found or capability token invalid");
        return json({jsonrpc:"2.0",id:rpc.id,result:{content:[{type:"text",text:JSON.stringify(data)}],structuredContent:data,isError:false}});
      } catch {
        return rpcError(rpc.id,-32000,"Task group status service unavailable");
      }
    }
    if (name === "assess_tool") {
      try {
        const data = assessTool(args);
        return json({ jsonrpc:"2.0", id:rpc.id, result:{content:[{type:"text",text:JSON.stringify(data)}],structuredContent:data,isError:data.status==="blocked"} });
      } catch (error) {
        return rpcError(rpc.id,-32602,error instanceof Error ? error.message : "Invalid tool assessment");
      }
    }
    if (name === "research_search") {
      try {
        const data = await researchSearch(args);
        return json({ jsonrpc:"2.0", id:rpc.id, result:{content:[{type:"text",text:JSON.stringify(data)}],structuredContent:data,isError:false} });
      } catch (error) {
        return rpcError(rpc.id,-32602,error instanceof Error ? error.message : "Scientific literature search failed");
      }
    }
    if (name === "browser_use_status") {
      if (Object.keys(args).length) return rpcError(rpc.id, -32602, "browser_use_status accepts no arguments");
      const status = {
        status: "not_configured", installed: false, ready: false,
        interactive_browser_ready: false, web_search_ready: false,
        web_fetch_ready: false, persistent_profiles: false,
        reason: "The Supabase Edge runtime does not currently host Browser Use, Chromium, or a persistent browser worker.",
        note: "Public web search and page extraction are not enabled in this deployment; interactive browser sessions, authenticated profiles, and JavaScript-rendered browsing are also inactive."
      };
      return json({ jsonrpc: "2.0", id: rpc.id, result: { content: [{type:"text",text:JSON.stringify(status)}], structuredContent: status, isError: false }});
    }
    const question = args.question;
    if (name !== "ask_flybrain" || typeof question !== "string" || !question.trim() || question.length > 12000) return rpcError(rpc.id, -32602, "Invalid tool or question");
    const research_context = await retrieve(question.trim());
    const result = {
      status: research_context.length ? "context_only" : "no_matching_context",
      answer_candidates: [],
      research_context,
      message: "No external language provider is configured. Use returned project evidence as context and let the connected ChatGPT model synthesize the response.",
      source_revision: BRANCH,
      source_count: SOURCES.length + archiveSourceCount,
      release_archive: archiveSourceCount ? "loaded" : "unavailable",
      release_archive_source_count: archiveSourceCount,
      release_archive_error: archiveLoadError,
      external_data_transfer: false
    };
    return json({ jsonrpc: "2.0", id: rpc.id, result: {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result,
      isError: false
    }});
  }
  return rpcError(rpc.id, -32601, "Method not found");
});
