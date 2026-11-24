"""Fail-closed data contract for the future EEC -> existing PGMQ adapter.

This module deliberately constructs identifiers-only queue messages. It does
not enqueue, claim, execute, or fetch task inputs.
"""
from __future__ import annotations

import uuid
from typing import Any


class EECQueueContractError(ValueError):
    """Raised when an EEC task does not satisfy the queue contract."""


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise EECQueueContractError(f"{field} must be a UUID string")
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise EECQueueContractError(f"{field} must be a UUID string") from None


def build_queue_message(task_id: str) -> dict[str, str]:
    """Return the minimal PGMQ message; never put run data or task text here."""
    return {"task_id": _uuid(task_id, "task_id")}


def build_queue_ledger_payload(run_id: str, task_id: str) -> dict[str, str]:
    """Return the only permitted task_runs payload for an EEC queue row."""
    return {
        "run_id": _uuid(run_id, "run_id"),
        "task_id": _uuid(task_id, "task_id"),
    }


def validate_claim(claim: dict[str, Any]) -> tuple[str, str, str]:
    """Validate the typed claim returned by the existing claim RPC."""
    if not isinstance(claim, dict) or claim.get("task_type") != "eec_agent":
        raise EECQueueContractError("claim is not an eec_agent task")
    payload = claim.get("payload")
    if not isinstance(payload, dict) or set(payload) != {"run_id", "task_id"}:
        raise EECQueueContractError("EEC queue payload must contain only run_id and task_id")
    run_id = _uuid(payload.get("run_id"), "run_id")
    task_id = _uuid(payload.get("task_id"), "task_id")
    if _uuid(claim.get("task_id"), "claim.task_id") != task_id:
        raise EECQueueContractError("queue task_id does not match EEC task_id")
    claim_token = _uuid(claim.get("claim_token"), "claim_token")
    if not isinstance(claim.get("message_id"), int) or claim["message_id"] < 1:
        raise EECQueueContractError("message_id must be a positive integer")
    return run_id, task_id, claim_token


def dependencies_satisfied(role: str, dependency_statuses: list[str]) -> bool:
    """Apply dependency gates; synthesis waits for independent acceptance."""
    if not isinstance(role, str) or not isinstance(dependency_statuses, list):
        return False
    if any(not isinstance(status, str) for status in dependency_statuses):
        return False
    if role == "synthesizer":
        allowed = {"reviewed", "accepted"}
    else:
        allowed = {"completed", "reviewed", "accepted"}
    return all(status in allowed for status in dependency_statuses)
