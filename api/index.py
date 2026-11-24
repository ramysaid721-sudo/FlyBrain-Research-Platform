"""Vercel Python serverless adapter for the FlyBrain MCP bridge.

The release archive is integrity-checked before extraction. The current bridge
overlay is copied from this repository into the extracted release at cold start.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = Path("/tmp/flybrain-release")
ARCHIVE = TMP_ROOT / "source.zip"
RELEASE_ROOT = TMP_ROOT / "FlyBrain_Research_Platform_v0.14.0"
ARCHIVE_URL = (
    "https://raw.githubusercontent.com/ramysaid721-sudo/"
    "FlyBrain-Research-Platform/894f219d04aedd1d4aeaaae5eb947af810165b8f/"
    "FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip"
)
EXPECTED_GIT_BLOB_SHA1 = "b02b9f10fb411bbcfd45418cfb51b9a548cc74a2"


def _ensure_release() -> None:
    if (RELEASE_ROOT / "components/FlyBrain-NOS/flybrain_os").is_dir():
        return
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    if not ARCHIVE.is_file():
        request = urllib.request.Request(
            ARCHIVE_URL, headers={"User-Agent": "FlyBrain-Vercel-MCP/1.0"}
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise RuntimeError("FlyBrain release archive exceeded the download limit")
        git_blob_sha1 = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes([0]) + data
        ).hexdigest()
        if git_blob_sha1 != EXPECTED_GIT_BLOB_SHA1:
            raise RuntimeError("FlyBrain release archive integrity check failed")
        ARCHIVE.write_bytes(data)
    with zipfile.ZipFile(ARCHIVE) as archive:
        root = TMP_ROOT.resolve()
        for member in archive.infolist():
            destination = (TMP_ROOT / member.filename).resolve()
            if destination != root and root not in destination.parents:
                raise RuntimeError("Unsafe path in FlyBrain release archive")
        archive.extractall(TMP_ROOT)

    package_root = RELEASE_ROOT / "components/FlyBrain-NOS/flybrain_os"
    overlay = ROOT / "bridge"
    package_root.mkdir(parents=True, exist_ok=True)
    for filename in ("chat_api.py", "mcp_server.py", "browser_use_adapter.py", "tool_manager.py", "eec_orchestrator.py", "eec_ledger_client.py"):
        source = overlay / filename
        if not source.is_file():
            raise RuntimeError("Missing FlyBrain bridge overlay: " + filename)
        shutil.copy2(source, package_root / filename)

    sys.path.insert(0, str(RELEASE_ROOT / "components/FlyBrain-NOS"))


def _create_app():
    _ensure_release()
    token = os.environ.get("FLYBRAIN_CHAT_API_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("FLYBRAIN_CHAT_API_TOKEN is not configured")
    from flybrain_os.chat_api import FlyBrainChatApp
    from flybrain_os.mcp_server import FlyBrainMCP

    ledger = os.environ.get("FLYBRAIN_CHAT_LEDGER", "/tmp/flybrain-chat.sqlite3")
    core = FlyBrainChatApp(token, ledger)
    mcp = FlyBrainMCP(core, token)

    def application(environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        routed_path = query.pop("__path", [environ.get("PATH_INFO", "/")])[0]
        environ["PATH_INFO"] = routed_path or "/"
        environ["QUERY_STRING"] = "&".join(
            key + "=" + value
            for key, values in query.items()
            for value in values
        )
        return mcp(environ, start_response)

    return application


app = _create_app()
