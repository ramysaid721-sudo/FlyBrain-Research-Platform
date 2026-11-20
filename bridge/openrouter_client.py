"""Authenticated, free-route-only client for the FlyBrain Supabase OpenRouter proxy."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .model_data_scanner import assert_external_model_payload_safe


class OpenRouterBridgeError(RuntimeError):
    """Safe, non-secret error returned by the staging proxy."""

    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
        super().__init__(code)


def _configuration() -> tuple[str, str]:
    endpoint = os.environ.get("SUPABASE_OPENROUTER_FUNCTION_URL", "").strip()
    token = os.environ.get("FLYBRAIN_OPENROUTER_BRIDGE_TOKEN", "")
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".supabase.co")
        or parsed.path != "/functions/v1/flybrain-openrouter"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or len(token) != 64
    ):
        raise OpenRouterBridgeError(503, "openrouter_bridge_not_configured")
    return endpoint, token


def generate_public_project_answer(
    question: str,
    context: str,
    *,
    timeout: int = 35,
) -> dict:
    """Send only screened public-project research to the free-only proxy."""
    if not isinstance(question, str) or not question.strip() or len(question) > 4_000:
        raise ValueError("question must be 1..4000 characters")
    if not isinstance(context, str) or len(context) > 16_000:
        raise ValueError("context must be at most 16000 characters")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 45:
        raise ValueError("timeout must be between 1 and 45 seconds")

    payload = {
        "scope": "public_project_research",
        "data_classification": "public",
        "question": question.strip(),
        "context": context,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > 24_000:
        raise ValueError("serialized public research payload exceeds 24 KB")

    # Defense-in-depth heuristic scanner. The caller restricts context to the
    # public repository retrieval allowlist; unknown/private content is rejected.
    assert_external_model_payload_safe(
        serialized_payload=serialized,
        data_class="public",
        contains_secrets=False,
        contains_personal_data=False,
    )

    endpoint, token = _configuration()
    request = Request(
        endpoint,
        data=serialized.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-flybrain-openrouter-token": token,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(32_769)
            status = response.status
    except HTTPError as exc:
        raw = exc.read(4_096)
        try:
            body = json.loads(raw.decode("utf-8"))
            code = body.get("error", "upstream_request_failed") if isinstance(body, dict) else "upstream_request_failed"
        except (UnicodeDecodeError, json.JSONDecodeError):
            code = "upstream_request_failed"
        raise OpenRouterBridgeError(exc.code, str(code)[:80]) from None
    except (URLError, TimeoutError, OSError):
        raise OpenRouterBridgeError(502, "openrouter_proxy_unavailable") from None

    if len(raw) > 32_768:
        raise OpenRouterBridgeError(502, "openrouter_response_too_large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OpenRouterBridgeError(502, "invalid_openrouter_proxy_response") from None
    if status < 200 or status >= 300:
        code = result.get("error", "openrouter_request_failed") if isinstance(result, dict) else "openrouter_request_failed"
        raise OpenRouterBridgeError(status, str(code)[:80])
    if (
        not isinstance(result, dict)
        or result.get("status") != "completed"
        or result.get("provider") != "openrouter"
        or result.get("requested_model_route") != "openrouter/free"
        or result.get("data_scope") != "public_project_research"
        or result.get("external_data_transfer") is not True
        or not isinstance(result.get("usage"), dict)
        or result["usage"].get("cost") != 0
        or not isinstance(result.get("served_model"), str)
        or not result["served_model"].endswith(":free")
        or not isinstance(result.get("answer"), str)
        or not result["answer"].strip()
    ):
        raise OpenRouterBridgeError(502, "invalid_openrouter_proxy_response")
    return result
