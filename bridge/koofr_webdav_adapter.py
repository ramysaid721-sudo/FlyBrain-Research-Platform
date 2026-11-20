"""Koofr WebDAV storage adapter with strict opt-in writes.

The adapter uses Koofr's documented WebDAV endpoint and application-specific
passwords. It never follows redirects, never logs credentials, and keeps writes
disabled unless both server configuration and per-call confirmation are present.
"""
from __future__ import annotations

import base64
import binascii
import os
import ssl
import urllib.error
import urllib.request
from urllib.parse import quote

KOOFR_WEBDAV_ENDPOINT = "https://app.koofr.net/dav/Koofr/"
MAX_OBJECT_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 15


class KoofrStorageError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _credentials() -> tuple[str, str]:
    username = os.environ.get("KOOFR_WEBDAV_USERNAME", "").strip()
    password = os.environ.get("KOOFR_WEBDAV_APP_PASSWORD", "")
    if not username or not password:
        raise KoofrStorageError("Koofr WebDAV credentials are not configured")
    return username, password


def _headers() -> dict[str, str]:
    username, password = _credentials()
    token = base64.b64encode((username + ":" + password).encode("utf-8")).decode("ascii")
    return {"Authorization": "Basic " + token, "User-Agent": "FlyBrain-USCL/1.0"}


def _object_url(object_key: str) -> str:
    if not isinstance(object_key, str) or not object_key or len(object_key) > 1024:
        raise ValueError("object_key must be a non-empty string of at most 1024 characters")
    if object_key.startswith("/") or "\\" in object_key or any(ord(ch) < 32 for ch in object_key):
        raise ValueError("object_key contains an unsafe path")
    parts = object_key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("object_key contains an unsafe path segment")
    return KOOFR_WEBDAV_ENDPOINT + "/".join(quote(part, safe="-_.~") for part in parts)


def _open(request: urllib.request.Request):
    opener = urllib.request.build_opener(
        _NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    return opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS)


def koofr_webdav_status() -> dict:
    configured = bool(
        os.environ.get("KOOFR_WEBDAV_USERNAME", "").strip()
        and os.environ.get("KOOFR_WEBDAV_APP_PASSWORD", "")
    )
    return {
        "provider": "koofr_webdav",
        "endpoint": KOOFR_WEBDAV_ENDPOINT,
        "configured": configured,
        "write_enabled": os.environ.get("FLYBRAIN_KOOFR_WEBDAV_ALLOW_WRITE", "").lower() == "true",
        "max_object_bytes": MAX_OBJECT_BYTES,
        "redirects_followed": False,
        "credentials_exposed": False,
        "ready": configured,
    }


def koofr_webdav_read(object_key: str) -> dict:
    url = _object_url(object_key)
    request = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with _open(request) as response:
            content = response.read(MAX_OBJECT_BYTES + 1)
            if len(content) > MAX_OBJECT_BYTES:
                raise KoofrStorageError("object exceeds the configured read limit")
            return {
                "status": "completed",
                "provider": "koofr_webdav",
                "object_key": object_key,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "size_bytes": len(content),
            }
    except urllib.error.HTTPError as exc:
        if exc.code in {301, 302, 303, 307, 308}:
            raise KoofrStorageError("WebDAV redirect rejected") from None
        raise KoofrStorageError("Koofr WebDAV read failed with HTTP " + str(exc.code)) from None
    except urllib.error.URLError:
        raise KoofrStorageError("Koofr WebDAV read could not reach the configured endpoint") from None


def koofr_webdav_write(object_key: str, content_base64: str, confirm_write: bool) -> dict:
    if confirm_write is not True:
        raise KoofrStorageError("per-call confirm_write=true is required")
    if os.environ.get("FLYBRAIN_KOOFR_WEBDAV_ALLOW_WRITE", "").lower() != "true":
        raise KoofrStorageError("Koofr WebDAV writes are disabled by server policy")
    if not isinstance(content_base64, str) or len(content_base64) > ((MAX_OBJECT_BYTES + 2) // 3) * 4 + 8:
        raise ValueError("content_base64 is invalid or exceeds the configured write limit")
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("content_base64 must be valid base64") from None
    if len(content) > MAX_OBJECT_BYTES:
        raise ValueError("object exceeds the configured write limit")
    url = _object_url(object_key)
    headers = _headers()
    headers["Content-Type"] = "application/octet-stream"
    request = urllib.request.Request(url, data=content, headers=headers, method="PUT")
    try:
        with _open(request) as response:
            status = getattr(response, "status", 200)
            if status not in {200, 201, 204}:
                raise KoofrStorageError("Koofr WebDAV write returned unexpected HTTP " + str(status))
            return {
                "status": "completed",
                "provider": "koofr_webdav",
                "object_key": object_key,
                "size_bytes": len(content),
                "write_enabled": True,
            }
    except urllib.error.HTTPError as exc:
        if exc.code in {301, 302, 303, 307, 308}:
            raise KoofrStorageError("WebDAV redirect rejected") from None
        raise KoofrStorageError("Koofr WebDAV write failed with HTTP " + str(exc.code)) from None
    except urllib.error.URLError:
        raise KoofrStorageError("Koofr WebDAV write could not reach the configured endpoint") from None
