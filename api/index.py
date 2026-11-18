"""Vercel serverless adapter for the existing FlyBrain read-only MCP bridge."""
from __future__ import annotations

import importlib
import os
import sys
import types
import zipfile
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip"
EXTRACT_ROOT = Path("/tmp/flybrain-release")
RELEASE_ROOT = EXTRACT_ROOT / "FlyBrain_Research_Platform_v0.14.0"


def _prepare_release() -> None:
    if RELEASE_ROOT.is_dir():
        return
    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as archive:
        base = EXTRACT_ROOT.resolve()
        for member in archive.infolist():
            target = (EXTRACT_ROOT / member.filename).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError("Unsafe path in FlyBrain release archive")
        archive.extractall(EXTRACT_ROOT)
    if not (RELEASE_ROOT / "components/FlyBrain-NOS/docs").is_dir():
        raise RuntimeError("Expected FlyBrain v0.14.0 release tree was not found")


_prepare_release()

# The bridge modules are the same tested modules used by the Render deployment.
# In provider-free mode the bridge deliberately returns source context to ChatGPT.
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
original_retriever = chat_api.retrieve_project_context


def _release_retriever(question: str, release_root=None, limit: int = 6):
    return original_retriever(question, release_root=RELEASE_ROOT, limit=limit)


chat_api.retrieve_project_context = _release_retriever
mcp_server = importlib.import_module("flybrain_os.mcp_server")

token = os.environ.get("FLYBRAIN_CHAT_API_TOKEN", "")
if len(token) < 32:
    raise RuntimeError("FLYBRAIN_CHAT_API_TOKEN must be configured as a Vercel secret")

_bridge = mcp_server.FlyBrainMCP(
    chat_api.FlyBrainChatApp(token, os.environ.get("FLYBRAIN_CHAT_LEDGER", "/tmp/flybrain-chat.sqlite3")),
    token,
)


def app(environ, start_response):
    # vercel.json rewrites all incoming paths to this function and preserves
    # the original path in __path__, so the existing WSGI routes stay unchanged.
    original_path = parse_qs(environ.get("QUERY_STRING", "")).get("__path", [None])[0]
    if original_path:
        environ["PATH_INFO"] = original_path
    return _bridge(environ, start_response)
