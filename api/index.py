"""Vercel serverless adapter for the repository's existing read-only MCP bridge."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import types
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


def _ensure_release() -> bool:
    if (RELEASE_ROOT / "components/FlyBrain-NOS/docs").is_dir():
        return True
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        if not ARCHIVE.is_file():
            request = urllib.request.Request(
                ARCHIVE_URL, headers={"User-Agent": "FlyBrain-Vercel-Bridge/1.0"}
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise RuntimeError("FlyBrain release archive exceeded the download limit")
            git_blob = hashlib.sha1(
                b"blob " + str(len(data)).encode("ascii") + bytes([0]) + data
            ).hexdigest()
            if git_blob != EXPECTED_GIT_BLOB_SHA1:
                raise RuntimeError("FlyBrain release archive integrity check failed")
            ARCHIVE.write_bytes(data)

        with zipfile.ZipFile(ARCHIVE) as archive:
            base = TMP_ROOT.resolve()
            for member in archive.infolist():
                target = (TMP_ROOT / member.filename).resolve()
                if target != base and base not in target.parents:
                    raise RuntimeError("Unsafe path in FlyBrain release archive")
            archive.extractall(TMP_ROOT)
        return (RELEASE_ROOT / "components/FlyBrain-NOS/docs").is_dir()
    except Exception:
        return False


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
_original_retriever = chat_api.retrieve_project_context


def _repo_fallback(question: str, limit: int = 6):
    terms = {word.strip(".,:;()[]{}\"'").lower() for word in question.split() if len(word) >= 3}
    ranked = []
    for path in sorted(ROOT.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for paragraph in raw.split(chr(10) + chr(10)):
            clean = " ".join(paragraph.split())
            if len(clean) < 45:
                continue
            words = {word.strip(".,:;()[]{}\"'").lower() for word in clean.split()}
            overlap = len(terms & words)
            if overlap:
                ranked.append((overlap, min(len(clean), 1400), path.name, clean[:1400]))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [
        {"source": source, "relevance_score": score, "excerpt": excerpt}
        for score, _length, source, excerpt in ranked[:limit]
    ]


def _retrieve_project_context(question: str, release_root=None, limit: int = 6):
    if _ensure_release():
        return _original_retriever(question, release_root=RELEASE_ROOT, limit=limit)
    return _repo_fallback(question, limit=limit)


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
    params = parse_qs(environ.get("QUERY_STRING", ""))
    original_path = params.get("__path", [None])[0]
    if original_path:
        environ["PATH_INFO"] = original_path
    if original_path == "/health" and params.get("check_corpus") == ["1"]:
        ready = _ensure_release()
        payload = {
            "status": "ok",
            "service": "flybrain-chat-bridge",
            "source_corpus": "full_release_archive" if ready else "repository_markdown_fallback",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        start_response("200 OK", [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ])
        return [body]
    return _bridge(environ, start_response)
