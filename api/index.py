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
    for filename in ("chat_api.py", "mcp_server.py", "browser_use_adapter.py", "tool_manager.py"):
        source = overlay / filename
        if not source.is_file():
            raise RuntimeError("Missing FlyBrain bridge overlay: " + filename)
        shutil.copy2(source, package_root / filename)

    sys.path.insert(0, str(RELEASE_ROOT / "components/FlyBrain-NOS"))



import hmac
import json
import re
import uuid
import urllib.error

STAGING_SCRIPT = "flybrain-research-platform-staging"
STAGING_SOURCE = "https://raw.githubusercontent.com/ramysaid721-sudo/FlyBrain-Research-Platform/main/cloudflare-staging/worker/index.ts"
STAGING_SOURCE_SHA = "296c735d6770f38ae7781a109e2315784cbd2482"


def _staging_reply(start_response, status, body, content_type="application/json; charset=utf-8"):
    payload = body.encode("utf-8") if isinstance(body, str) else body
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(payload))),
        ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"), ("X-Frame-Options", "DENY")])
    return [payload]


def _staging_page():
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FlyBrain staging setup</title><style>body{font:16px system-ui;max-width:650px;margin:40px auto;padding:0 18px;background:#101827;color:#eef2ff}main{background:#182438;border:1px solid #34445d;border-radius:14px;padding:24px}label{display:block;margin:18px 0 7px;font-weight:600}input{box-sizing:border-box;width:100%;padding:12px;border-radius:8px;border:1px solid #52627a;background:#0d1727;color:white}button{margin-top:20px;padding:12px 18px;border:0;border-radius:8px;background:#8bc5ff;color:#09203b;font-weight:700}small{color:#b8c5d8}#out{white-space:pre-wrap;overflow-wrap:anywhere;margin-top:18px}</style>
<main><h1>FlyBrain staging deployment</h1><p>Enter the Cloudflare credentials here. They are transmitted over HTTPS for this deployment only and are not stored or logged by this endpoint. Do not paste them into ChatGPT.</p>
<form id="f"><label>Cloudflare Account ID</label><input id="a" required pattern="[a-fA-F0-9]{32}" maxlength="32" autocomplete="off" placeholder="32-character account ID">
<label>Cloudflare API Token</label><input id="t" type="password" required minlength="20" autocomplete="off" placeholder="Workers Scripts Write token">
<small>Required permission: Account → Workers Scripts → Edit.</small><br><button id="b">Deploy staging Worker</button></form><div id="out" role="status"></div></main>
<script>const f=document.getElementById('f'),o=document.getElementById('out'),b=document.getElementById('b');f.onsubmit=async e=>{e.preventDefault();const k=location.hash.slice(1);if(!k){o.textContent='Invalid setup link: access key missing.';return;}b.disabled=true;o.textContent='Checking credentials and deploying…';try{const r=await fetch('/__cloudflare_staging_setup',{method:'POST',headers:{'content-type':'application/json','authorization':'Bearer '+k},body:JSON.stringify({account_id:document.getElementById('a').value.trim(),api_token:document.getElementById('t').value.trim()})});const d=await r.json();document.getElementById('t').value='';if(!r.ok)throw Error(d.error||'Deployment failed');o.textContent=JSON.stringify(d,null,2);history.replaceState(null,'',location.pathname);}catch(x){o.textContent='Deployment failed: '+x.message;}finally{b.disabled=false;}};</script></html>"""


def _cf_call(account_id, token, path, method="GET", body=None, content_type="application/json"):
    url = "https://api.cloudflare.com/client/v4/accounts/" + account_id + path
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read(1000001)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read(100000).decode("utf-8", "replace"))
            message = "; ".join(x.get("message", "Cloudflare API error") for x in payload.get("errors", []))
        except Exception:
            message = "Cloudflare API returned HTTP " + str(exc.code)
        raise RuntimeError(message[:600] or "Cloudflare API request failed")
    data = json.loads(raw.decode("utf-8"))
    if not data.get("success"):
        raise RuntimeError("; ".join(x.get("message", "Cloudflare API error") for x in data.get("errors", []))[:600])
    return data.get("result") or {}


def _deploy_staging_worker(account_id, token):
    req = urllib.request.Request(STAGING_SOURCE, headers={"User-Agent": "FlyBrain-Staging-Bridge/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        source = response.read(100001)
    digest = hashlib.sha1(b"blob " + str(len(source)).encode("ascii") + bytes([0]) + source).hexdigest()
    if digest != STAGING_SOURCE_SHA:
        raise RuntimeError("Pinned Worker source integrity check failed")
    metadata = {"main_module":"index.js","compatibility_date":"2026-11-18","bindings":[{
        "type":"ratelimit","name":"FLYBRAIN_PUBLIC_LIMITER","namespace_id":"26111702",
        "simple":{"limit":30,"period":60}}]}
    boundary = "----FlyBrain" + uuid.uuid4().hex
    parts = [
        ("--"+boundary+"\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n").encode()+json.dumps(metadata).encode()+b"\r\n",
        ("--"+boundary+"\r\nContent-Disposition: form-data; name=\"index.js\"; filename=\"index.js\"\r\nContent-Type: application/javascript+module\r\n\r\n").encode()+source+b"\r\n",
        ("--"+boundary+"--\r\n").encode()]
    uploaded = _cf_call(account_id, token, "/workers/scripts/"+STAGING_SCRIPT, "PUT", b"".join(parts), "multipart/form-data; boundary="+boundary)
    subdomain = _cf_call(account_id, token, "/workers/subdomain").get("subdomain")
    if not subdomain:
        raise RuntimeError("Worker uploaded, but this account has no workers.dev subdomain configured.")
    _cf_call(account_id, token, "/workers/scripts/"+STAGING_SCRIPT+"/subdomain", "POST", json.dumps({"enabled":True}).encode())
    url = "https://"+STAGING_SCRIPT+"."+subdomain+".workers.dev"
    try:
        with urllib.request.urlopen(url+"/health", timeout=12) as response:
            health = json.loads(response.read(100000).decode())
    except Exception:
        health = {"status":"not_yet_verified"}
    return {"deployed":True,"worker_url":url,"health":health,"rate_limit_binding_configured":True,
            "script_id":uploaded.get("id",STAGING_SCRIPT)}


def _staging_setup_handler(environ, start_response):
    if environ.get("REQUEST_METHOD") == "GET":
        return _staging_reply(start_response,"200 OK",_staging_page(),"text/html; charset=utf-8")
    if environ.get("REQUEST_METHOD") != "POST":
        return _staging_reply(start_response,"405 Method Not Allowed",json.dumps({"error":"Method not allowed"}))
    expected = os.environ.get("FLYBRAIN_STAGING_BRIDGE_KEY","")
    header = environ.get("HTTP_AUTHORIZATION","")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    if not expected or not supplied or not hmac.compare_digest(expected,supplied):
        return _staging_reply(start_response,"401 Unauthorized",json.dumps({"error":"Unauthorized"}))
    try:
        size = int(environ.get("CONTENT_LENGTH") or "0")
        if size <= 0 or size > 12000: raise ValueError("Invalid request size")
        payload = json.loads(environ["wsgi.input"].read(size).decode())
        account = str(payload.get("account_id","")).strip()
        token = str(payload.get("api_token","")).strip()
        if not re.fullmatch(r"[a-fA-F0-9]{32}",account): raise ValueError("Account ID must be 32 hexadecimal characters.")
        if not 20 <= len(token) <= 500: raise ValueError("API Token has an invalid length.")
        result = _deploy_staging_worker(account,token)
        return _staging_reply(start_response,"200 OK",json.dumps(result))
    except Exception as exc:
        message = str(exc)
        if "authorization" in message.lower() or "token" in message.lower():
            message = "Cloudflare rejected the credentials or token scope. Confirm Workers Scripts Write permission."
        return _staging_reply(start_response,"400 Bad Request",json.dumps({"error":message[:700]}))



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
        if environ["PATH_INFO"] == "/__cloudflare_staging_setup":
            return _staging_setup_handler(environ, start_response)
        return mcp(environ, start_response)

    return application


app = _create_app()
