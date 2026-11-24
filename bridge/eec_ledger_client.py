"""Narrow authenticated client for the Staging EEC plan ledger.

Only hashes, role/task metadata, and dependency identifiers are sent. The raw
objective is deliberately removed before the request leaves the MCP process.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from typing import Any

EXPECTED_HOST = "iudimypauqbkyvjuprgp.supabase.co"
EXPECTED_PATH = "/functions/v1/flybrain-eec-ledger"
PLAN_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)


class EECLedgerError(RuntimeError):
    """Raised when the Staging ledger rejects or cannot complete a request."""


def _configuration() -> tuple[str, str]:
    endpoint = os.environ.get("SUPABASE_EEC_LEDGER_URL", "").strip()
    token = os.environ.get("FLYBRAIN_EEC_LEDGER_TOKEN", "").strip()
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or parsed.hostname != EXPECTED_HOST
        or parsed.path != EXPECTED_PATH
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or len(token) < 32
    ):
        return "", ""
    return endpoint, token


def ledger_status() -> dict[str, Any]:
    endpoint, token = _configuration()
    return {
        "configured": bool(endpoint and token),
        "endpoint_configured": bool(endpoint),
        "credential_configured": bool(token),
        "environment": "staging",
        "live_agent_execution": False,
        "provider_inference": False,
    }


def _call(payload: dict[str, Any]) -> dict[str, Any]:
    endpoint, token = _configuration()
    if not endpoint or not token:
        return {
            "status": "not_connected",
            "reason": "Staging EEC ledger credentials are not configured for this deployment.",
            "live_agent_execution": False,
        }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-flybrain-worker-token": token,
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            if getattr(response, "status", 200) != 200:
                raise EECLedgerError("EEC ledger returned an unexpected HTTP status")
            raw = response.read(65537)
    except HTTPError as exc:
        raise EECLedgerError(f"EEC ledger HTTP error {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise EECLedgerError("EEC ledger is temporarily unavailable") from None
    if len(raw) > 65536:
        raise EECLedgerError("EEC ledger response exceeded the size limit")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EECLedgerError("EEC ledger returned invalid JSON") from None
    if not isinstance(result, dict):
        raise EECLedgerError("EEC ledger returned an invalid response")
    return result


def persist_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise EECLedgerError("A plan object is required")
    safe_plan = {key: value for key, value in plan.items() if key != "objective"}
    return _call({"action": "persist_plan", "plan": safe_plan})


def get_plan_status(plan_id: str) -> dict[str, Any]:
    if not isinstance(plan_id, str) or not PLAN_ID_RE.fullmatch(plan_id):
        raise EECLedgerError("A valid plan UUID is required")
    return _call({"action": "plan_status", "plan_id": plan_id})
