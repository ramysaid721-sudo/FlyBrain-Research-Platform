"""Vercel serverless adapter for the repository's existing read-only MCP bridge."""
from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]

package = types.ModuleType("flybrain_os")
package.__path__ = [str(ROOT / "bridge")]
sys.modules.setdefault("flybrain_os", package)

model_hub = types.ModuleType("flybrain_os.model_hub")


class _NoExternalProviders:
    def __init__(self, *_args, **_kwargs):
        pass

    def consult(self, *_args, **_kwargs):
        return {"status": "no_providers_configured", "results": []}


model_hub.ModelConsultation = _NoExternalProviders
sys.modules.setdefault("flybrain_os.model_hub", model_hub)

chat_api = importlib.import_module("flybrain_os.chat_api")
mcp_server = importlib.import_module("flybrain_os.mcp_server")


def _retrieve_project_context(question: str, release_root=None, limit: int = 6):
    terms = {word.strip(".,:;()[]{}\"'").lower() for word in question.split() if len(word) >= 3}
    ranked = []
    for path in sorted(ROOT.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for paragraph in raw.split("\n\n"):
            clean = " ".join(paragraph.split())
            if len(clean) < 45:
                continue
            words = {word.strip(".,:;()[]{}\"'").lower() for word in clean.split()}
            overlap = len(terms & words)
            if overlap:
                ranked.append((overlap, min(len(clean), 1400), path.name, clean[:1400]))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    seen, results = set(), []
    for score, _length, source, excerpt in ranked:
        key = (source, excerpt[:160])
        if key in seen:
            continue
        seen.add(key)
        results.append({"source": source, "relevance_score": score, "excerpt": excerpt})
        if len(results) >= limit:
            break
    return results


chat_api.retrieve_project_context = _retrieve_project_context

token = os.environ.get("FLYBRAIN_CHAT_API_TOKEN", "")
if len(token) < 32:
    raise RuntimeError("FLYBRAIN_CHAT_API_TOKEN must be configured as a Vercel secret")

_bridge = mcp_server.FlyBrainMCP(
    chat_api.FlyBrainChatApp(
        token, os.environ.get("FLYBRAIN_CHAT_LEDGER", "/tmp/flybrain-chat.sqlite3")
    ),
    token,
)


def app(environ, start_response):
    original_path = parse_qs(environ.get("QUERY_STRING", "")).get("__path", [None])[0]
    if original_path:
        environ["PATH_INFO"] = original_path
    return _bridge(environ, start_response)
