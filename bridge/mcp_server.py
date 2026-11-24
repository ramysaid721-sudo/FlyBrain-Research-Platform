"""Authenticated MCP facade for FlyBrain research and browser automation."""
from __future__ import annotations
import hmac, io, json, os, time
from collections import defaultdict, deque
from threading import Lock
from wsgiref.simple_server import make_server
from .chat_api import FlyBrainChatApp
from .tool_manager import ToolPolicyError, tool_manager_status, tool_catalog, assess_tool
from .eec_orchestrator import EECPlanError, eec_status, build_plan
from .eec_ledger_client import EECLedgerError, ledger_status, persist_plan, get_plan_status

class FlyBrainMCP:
    def __init__(self, app: FlyBrainChatApp, token: str):
        self.app, self.token = app, token
        self._public_calls = defaultdict(deque)
        self._public_lock = Lock()

    @staticmethod
    def send(start, status, payload=None):
        if payload is None:
            start(status, [("Content-Length", "0"), ("Cache-Control", "no-store")])
            return [b""]
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        start(status, [("Content-Type", "application/json; charset=utf-8"),
                       ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                       ("X-Content-Type-Options", "nosniff")])
        return [body]

    @staticmethod
    def _tool_result(mid, data, is_error=False):
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
            "structuredContent": data, "isError": is_error}}

    def __call__(self, env, start):
        path = env.get("PATH_INFO", "")
        method = env.get("REQUEST_METHOD", "GET").upper()
        if path in {"/", "/health"} and method == "GET":
            from .browser_use_adapter import browser_use_status
            browser = browser_use_status()
            return self.send(start, "200 OK", {
                "status": "ok",
                "service": "flybrain-mcp",
                "version": "0.16.0",
                "mcp_endpoint": "/mcp",
                "tools": ["ask_flybrain", "browser_search", "browser_fetch", "browser_research", "browser_use_status", "browser_run_task", "tool_manager_status", "tool_catalog", "assess_tool", "eec_status", "eec_plan", "eec_submit_plan", "eec_plan_status"],
                "capabilities": {
                    "project_retrieval": True,
                    "public_web_search": True,
                    "public_page_extraction": True,
                    "multi_source_research": True,
                    "interactive_browser": browser.get("interactive_browser_ready", False),
                    "persistent_browser_profiles": False,
                    "eec_planning": True,
                    "eec_durable_plan_submission": ledger_status()["configured"]
                },
                "browser_status": browser
            })
        if path != "/mcp":
            return self.app(env, start)
        if env.get("REQUEST_METHOD", "GET").upper() != "POST":
            start("405 Method Not Allowed", [("Allow", "POST"), ("Content-Length", "0")])
            return [b""]
        auth = env.get("HTTP_AUTHORIZATION", "")
        supplied = auth[7:] if auth.startswith("Bearer ") else ""
        try:
            n = int(env.get("CONTENT_LENGTH") or "0")
            if n < 1 or n > 32768:
                return self.send(start, "413 Payload Too Large", {"error": "invalid_body_size"})
            req = json.loads(env["wsgi.input"].read(n).decode())
            if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
                return self.send(start, "400 Bad Request", {"error": "invalid_json_rpc_request"})
            mid, method = req.get("id"), req["method"]
            if mid is None and method.startswith("notifications/"):
                return self.send(start, "202 Accepted")
            params = req.get("params") or {}
            tool_name = params.get("name") if method == "tools/call" else None
            public_methods = {"initialize", "ping", "tools/list"}
            public_tools = {"ask_flybrain", "browser_search", "browser_fetch", "browser_research", "browser_use_status", "tool_manager_status", "tool_catalog", "assess_tool", "eec_status", "eec_plan"}
            public_request = method in public_methods or (method == "tools/call" and tool_name in public_tools)
            if not public_request and not hmac.compare_digest(supplied, self.token):
                return self.send(start, "401 Unauthorized", {"error": "unauthorized"})
            if public_request:
                forwarded = env.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                client = env.get("HTTP_X_REAL_IP") or env.get("REMOTE_ADDR") or forwarded or "unknown"
                now = time.monotonic()
                with self._public_lock:
                    calls = self._public_calls[client]
                    while calls and now - calls[0] > 60:
                        calls.popleft()
                    if len(calls) >= 60:
                        return self.send(start, "429 Too Many Requests", {"error": "public_rate_limit_exceeded", "retry_after_seconds": 60})
                    calls.append(now)
            if method == "initialize":
                requested = (req.get("params") or {}).get("protocolVersion", "2025-03-26")
                version = requested if requested in {"2024-11-05", "2025-03-26", "2025-06-18"} else "2025-03-26"
                result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "flybrain-research-bridge", "version": "0.16.0"},
                          "instructions": "Call ask_flybrain automatically for any request that depends on FlyBrain-NOS, URCAL, the FlyBrain project repository, its architecture, implementation, status, evidence, integrations, or project decisions, even if the user does not type the words FlyBrain or ذبابة. Do not call it for unrelated general questions. Use browser_search, browser_fetch, and browser_research for public HTTP research and page extraction; these do not execute JavaScript. Use browser_use_status to inspect interactive browser readiness; browser_run_task requires a separately configured browser host, model, and token. Apply least privilege. Passive reconnaissance and defensive analysis must stay within authorized assets; active scans and exploit validation require explicit scope and approval. Side effects require explicit approval. Distinguish retrieved evidence from inference and report capability limitations honestly."}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": [
                    {"name": "ask_flybrain", "title": "Ask FlyBrain research system",
                     "description": "Automatically use this tool whenever a user asks about FlyBrain, FlyBrain-NOS, URCAL, the Gaza Jar research context explicitly linked to this project, its architecture, code, capabilities, status, evidence, integrations, or next steps—even when the user does not say “FlyBrain” or “ذبابة”. Retrieve source-labelled project evidence and distinguish documented facts from inference.",
                     "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "minLength": 1, "maxLength": 12000}}, "required": ["question"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": True}},
                    {"name": "browser_search", "title": "Search the public web",
                     "description": "Search public web results through DuckDuckGo HTML and return titles, snippets, and exact URLs. Uses safe HTTPS fetching; no Browser Use dependency or external LLM is required.",
                     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 1500}, "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8}}, "required": ["query"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": True}},
                    {"name": "browser_fetch", "title": "Fetch public webpage content",
                     "description": "Fetch a public HTTPS page and extract readable HTML/text content, title, description, and source links. This HTTP mode does not execute JavaScript or render dynamic pages.",
                     "inputSchema": {"type": "object", "properties": {"url": {"type": "string", "format": "uri", "maxLength": 2048}, "output_format": {"type": "string", "enum": ["markdown", "text", "json"], "default": "markdown"}, "include_links": {"type": "boolean", "default": True}}, "required": ["url"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": True}},
                    {"name": "browser_research", "title": "Multi-source web research",
                     "description": "Search public web results and fetch multiple source pages, returning excerpts and exact URLs for ChatGPT to synthesize. No Browser Use runtime or external model is required.",
                     "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "minLength": 1, "maxLength": 4000}, "max_sources": {"type": "integer", "minimum": 2, "maximum": 6, "default": 6}}, "required": ["question"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": True}},
                    {"name": "browser_use_status", "title": "Browser automation readiness",
                     "description": "Check interactive Browser Use readiness separately from the HTTP search and fetch capabilities. This does not launch a browser.",
                     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
                    {"name": "tool_manager_status", "title": "Tool lifecycle manager status",
                     "description": "Report the FlyBrain tool manager mode, security controls, and whether an isolated installation worker is available.",
                     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
                    {"name": "tool_catalog", "title": "Approved tool candidates",
                     "description": "List narrowly allowlisted low-risk tool candidates and blocked high-impact examples. Does not install tools.",
                     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
                    {"name": "assess_tool", "title": "Assess a tool candidate",
                     "description": "Apply FlyBrain's fail-closed policy to a candidate package. Assessment never installs or executes the candidate.",
                     "inputSchema": {"type": "object", "properties": {
                         "name": {"type": "string", "minLength": 1, "maxLength": 100},
                         "version": {"type": "string", "maxLength": 80},
                         "source": {"type": "string", "maxLength": 300}},
                         "required": ["name"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
                    {"name": "eec_status", "title": "EEC orchestration readiness",
                     "description": "Report EEC planning readiness, role catalog, zero-cost policy, and execution blockers. Does not invoke agents or providers.",
                     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
                    {"name": "eec_plan", "title": "Build a bounded EEC execution plan",
                     "description": "Decompose a research or engineering objective into bounded role assignments, dependencies, execution waves, and acceptance criteria. Planning only; no agent or provider is invoked.",
                     "inputSchema": {"type": "object", "properties": {
                         "objective": {"type": "string", "minLength": 1, "maxLength": 8000},
                         "task_kind": {"type": "string", "enum": ["general", "research", "engineering", "security", "performance", "documentation"], "default": "general"},
                         "data_classification": {"type": "string", "enum": ["public", "internal", "confidential", "prohibited"], "default": "internal"},
                         "max_parallel_tasks": {"type": "integer", "minimum": 1, "maximum": 4, "default": 3}},
                         "required": ["objective"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
                    {"name": "eec_submit_plan", "title": "Persist an EEC plan to Staging",
                     "description": "Build and persist a bounded EEC plan in the authenticated Staging ledger. Stores hashes and task metadata only; does not execute agents or contact model providers.",
                     "inputSchema": {"type": "object", "properties": {
                         "objective": {"type": "string", "minLength": 1, "maxLength": 8000},
                         "task_kind": {"type": "string", "enum": ["general", "research", "engineering", "security", "performance", "documentation"], "default": "general"},
                         "data_classification": {"type": "string", "enum": ["public", "internal", "confidential"], "default": "internal"},
                         "max_parallel_tasks": {"type": "integer", "minimum": 1, "maximum": 4, "default": 3}},
                         "required": ["objective"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": False, "openWorldHint": False}},
                    {"name": "eec_plan_status", "title": "Read EEC plan status",
                     "description": "Read status counts for a persisted Staging EEC plan. Requires authenticated access.",
                     "inputSchema": {"type": "object", "properties": {
                         "plan_id": {"type": "string", "format": "uuid"}},
                         "required": ["plan_id"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
                    {"name": "browser_run_task", "title": "Run a browser task",
                     "description": "Run a bounded interactive Browser Use task on an authorized public HTTPS website. Requires Browser Use, Chromium, and a reachable configured model on a compatible browser host. Does not bypass logins, CAPTCHAs, paywalls, or access controls. Account changes, submissions, purchases, publishing, deletion, and other side effects are blocked unless allow_side_effects is explicitly true.",
                     "inputSchema": {"type": "object", "properties": {
                         "url": {"type": "string", "format": "uri", "maxLength": 2048},
                         "goal": {"type": "string", "minLength": 1, "maxLength": 8000},
                         "max_steps": {"type": "integer", "minimum": 1, "maximum": 30, "default": 12},
                         "allow_side_effects": {"type": "boolean", "default": False}},
                         "required": ["url", "goal"], "additionalProperties": False},
                     "annotations": {"readOnlyHint": False, "openWorldHint": True}}
                ]}
            elif method == "tools/call":
                p = req.get("params") or {}
                args = p.get("arguments") or {}
                name = p.get("name")
                if name == "tool_manager_status":
                    if args:
                        raise ValueError("tool_manager_status accepts no arguments")
                    return self.send(start, "200 OK", self._tool_result(mid, tool_manager_status()))
                if name == "eec_status":
                    if args:
                        raise ValueError("eec_status accepts no arguments")
                    return self.send(start, "200 OK", self._tool_result(mid, eec_status()))
                if name == "eec_plan":
                    if set(args) - {"objective", "task_kind", "data_classification", "max_parallel_tasks"}:
                        raise ValueError("Unexpected eec_plan argument")
                    try:
                        plan = build_plan(args.get("objective"), args.get("task_kind", "general"),
                                          args.get("data_classification", "internal"),
                                          args.get("max_parallel_tasks", 3))
                    except EECPlanError as exc:
                        raise ValueError(str(exc)) from exc
                    return self.send(start, "200 OK", self._tool_result(mid, plan))
                if name == "eec_submit_plan":
                    if set(args) - {"objective", "task_kind", "data_classification", "max_parallel_tasks"}:
                        raise ValueError("Unexpected eec_submit_plan argument")
                    try:
                        plan = build_plan(args.get("objective"), args.get("task_kind", "general"),
                                          args.get("data_classification", "internal"),
                                          args.get("max_parallel_tasks", 3))
                        result = persist_plan(plan)
                    except EECPlanError as exc:
                        raise ValueError(str(exc)) from exc
                    except EECLedgerError as exc:
                        return self.send(start, "503 Service Unavailable",
                                         self._tool_result(mid, {"status": "ledger_unavailable", "reason": str(exc)}, True))
                    if result.get("status") != "ok":
                        return self.send(start, "503 Service Unavailable", self._tool_result(mid, result, True))
                    return self.send(start, "200 OK", self._tool_result(mid, result))
                if name == "eec_plan_status":
                    if set(args) != {"plan_id"} or not isinstance(args.get("plan_id"), str):
                        raise ValueError("eec_plan_status requires plan_id")
                    try:
                        result = get_plan_status(args["plan_id"])
                    except EECLedgerError as exc:
                        return self.send(start, "503 Service Unavailable",
                                         self._tool_result(mid, {"status": "ledger_unavailable", "reason": str(exc)}, True))
                    if result.get("status") != "ok":
                        return self.send(start, "404 Not Found", self._tool_result(mid, result, True))
                    return self.send(start, "200 OK", self._tool_result(mid, result))
                if name == "tool_catalog":
                    if args:
                        raise ValueError("tool_catalog accepts no arguments")
                    return self.send(start, "200 OK", self._tool_result(mid, tool_catalog()))
                if name == "assess_tool":
                    if set(args) - {"name", "version", "source"} or not isinstance(args.get("name"), str):
                        raise ValueError("assess_tool requires name and accepts only version/source")
                    try:
                        assessed = assess_tool(args["name"], args.get("version", ""), args.get("source", ""))
                    except ToolPolicyError as exc:
                        raise ValueError(str(exc)) from exc
                    return self.send(start, "200 OK", self._tool_result(mid, assessed, assessed.get("status") == "blocked"))
                if name == "ask_flybrain":
                    q = args.get("question")
                    if not isinstance(q, str) or not q.strip() or len(q) > 12000:
                        return self.send(start, "200 OK", {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "Invalid question"}})
                    raw = json.dumps({"question": q.strip()}).encode()
                    inner = dict(env)
                    inner.update({"REQUEST_METHOD": "POST", "PATH_INFO": "/v1/ask", "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw), "HTTP_AUTHORIZATION": "Bearer " + self.token})
                    captured = {}
                    def inner_start(status, headers): captured["status"] = status
                    body = b"".join(self.app(inner, inner_start))
                    data = json.loads(body.decode())
                    return self.send(start, "200 OK", self._tool_result(mid, data, not captured.get("status", "").startswith("200")))
                if name in {"browser_search", "browser_fetch", "browser_research", "browser_use_status", "browser_run_task"}:
                    from .browser_use_adapter import (BrowserUseNotConfigured, browser_use_status, run_browser_task,
                        run_browser_search, run_browser_fetch, run_browser_research)
                    try:
                        if name == "browser_use_status":
                            if args:
                                raise ValueError("browser_use_status accepts no arguments")
                            data = browser_use_status()
                        elif name == "browser_search":
                            if set(args) - {"query", "max_results"}:
                                raise ValueError("Unexpected browser_search argument")
                            data = run_browser_search(args.get("query"), args.get("max_results", 8))
                        elif name == "browser_fetch":
                            if set(args) - {"url", "output_format", "include_links"}:
                                raise ValueError("Unexpected browser_fetch argument")
                            data = run_browser_fetch(args.get("url"), args.get("output_format", "markdown"), args.get("include_links", True))
                        elif name == "browser_research":
                            if set(args) - {"question", "max_sources"}:
                                raise ValueError("Unexpected browser_research argument")
                            data = run_browser_research(args.get("question"), args.get("max_sources", 6))
                        else:
                            url, goal = args.get("url"), args.get("goal")
                            if set(args) - {"url", "goal", "max_steps", "allow_side_effects"}:
                                raise ValueError("Unexpected browser_run_task argument")
                            data = run_browser_task(url, goal, args.get("max_steps", 12), args.get("allow_side_effects", False))
                        return self.send(start, "200 OK", self._tool_result(mid, data, data.get("status") in {"error"}))
                    except (ValueError, BrowserUseNotConfigured) as exc:
                        return self.send(start, "200 OK", self._tool_result(mid, {"status": "not_ready", "error": str(exc)}, True))
                return self.send(start, "200 OK", {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "Unknown tool"}})
            else:
                return self.send(start, "200 OK", {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}})
            return self.send(start, "200 OK", {"jsonrpc": "2.0", "id": mid, "result": result})
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return self.send(start, "400 Bad Request", {"error": "invalid_request"})
        except Exception:
            return self.send(start, "500 Internal Server Error", {"error": "mcp_request_failed"})

def main():
    token = os.environ.get("FLYBRAIN_CHAT_API_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("FLYBRAIN_CHAT_API_TOKEN must contain at least 32 characters")
    base = FlyBrainChatApp(token, os.environ.get("FLYBRAIN_CHAT_LEDGER", "/tmp/flybrain-chat.sqlite3"))
    app = FlyBrainMCP(base, token)
    with make_server("0.0.0.0", int(os.environ.get("PORT", "10000")), app) as server:
        server.serve_forever()

if __name__ == "__main__":
    main()
