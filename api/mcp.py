"""Vercel Python WSGI entrypoint for the stateless FlyBrain MCP bridge."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / ".release" / "FlyBrain_Research_Platform_v0.14.0"
PACKAGE_ROOT = RELEASE_ROOT / "components" / "FlyBrain-NOS"

if not (PACKAGE_ROOT / "flybrain_os" / "mcp_server.py").is_file():
    raise RuntimeError(
        "FlyBrain release package is missing. The Vercel install command must "
        "extract the release archive and apply the bridge overlay first."
    )

sys.path.insert(0, str(PACKAGE_ROOT))

from flybrain_os.chat_api import FlyBrainChatApp  # noqa: E402
from flybrain_os.mcp_server import FlyBrainMCP  # noqa: E402

TOKEN = os.environ.get("FLYBRAIN_CHAT_API_TOKEN", "")
if len(TOKEN) < 32:
    raise RuntimeError("FLYBRAIN_CHAT_API_TOKEN must contain at least 32 characters")

base_app = FlyBrainChatApp(
    TOKEN,
    os.environ.get("FLYBRAIN_CHAT_LEDGER", "/tmp/flybrain-chat.sqlite3"),
)
mcp_app = FlyBrainMCP(base_app, TOKEN)


class VercelMCPApplication:
    """Adapt Vercel's function route path to the existing WSGI MCP endpoint."""

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path in ("", "/", "/api/mcp", "/mcp"):
            environ = dict(environ)
            environ["PATH_INFO"] = "/mcp"
        return mcp_app(environ, start_response)


app = VercelMCPApplication()
