"""Stateless MCP Streamable HTTP facade for the FlyBrain research bridge."""
from __future__ import annotations
import hmac, io, json, os
from wsgiref.simple_server import make_server
from .chat_api import FlyBrainChatApp

class FlyBrainMCP:
    def __init__(self, app: FlyBrainChatApp, token: str):
        self.app, self.token = app, token

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

    def __call__(self, env, start):
        if env.get("PATH_INFO") != "/mcp":
            return self.app(env, start)
        if env.get("REQUEST_METHOD", "GET").upper() != "POST":
            start("405 Method Not Allowed", [("Allow", "POST"), ("Content-Length", "0")])
            return [b""]
        auth = env.get("HTTP_AUTHORIZATION", "")
        supplied = auth[7:] if auth.startswith("Bearer ") else ""
        if not hmac.compare_digest(supplied, self.token):
            return self.send(start, "401 Unauthorized", {"error": "unauthorized"})
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
            if method == "initialize":
                requested = (req.get("params") or {}).get("protocolVersion", "2025-03-26")
                version = requested if requested in {"2024-11-05", "2025-03-26", "2025-06-18"} else "2025-03-26"
                result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "flybrain-research-bridge", "version": "0.14.0"},
                          "instructions": "Call ask_flybrain for project research. Distinguish source evidence from hypotheses; the synthetic LIF runtime is not a validated biological language model."}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": [{"name": "ask_flybrain", "title": "Ask FlyBrain research system",
                    "description": "Retrieve source-labelled FlyBrain-NOS and URCAL context and optionally consult configured ModelHub providers. Without a provider, return local evidence for ChatGPT to synthesize.",
                    "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "minLength": 1, "maxLength": 12000}},
                                    "required": ["question"], "additionalProperties": False},
                    "annotations": {"readOnlyHint": True, "openWorldHint": True}}]}
            elif method == "tools/call":
                p = req.get("params") or {}
                args = p.get("arguments") or {}
                q = args.get("question")
                if p.get("name") != "ask_flybrain" or not isinstance(q, str) or not q.strip() or len(q) > 12000:
                    return self.send(start, "200 OK", {"jsonrpc": "2.0", "id": mid,
                        "error": {"code": -32602, "message": "Invalid tool or question"}})
                raw = json.dumps({"question": q.strip()}).encode()
                inner = dict(env)
                inner.update({"REQUEST_METHOD": "POST", "PATH_INFO": "/v1/ask",
                    "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw),
                    "HTTP_AUTHORIZATION": auth})
                captured = {}
                def inner_start(status, headers):
                    captured["status"] = status
                body = b"".join(self.app(inner, inner_start))
                data = json.loads(body.decode())
                result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                          "structuredContent": data,
                          "isError": not captured.get("status", "").startswith("200")}
            else:
                return self.send(start, "200 OK", {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32601, "message": "Method not found"}})
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
