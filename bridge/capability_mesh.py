"""Bounded capability registry and privacy-aware task router.

This module plans routes only. It does not invoke providers, transfer data,
install tools, spend money, or perform side effects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}


@dataclass(frozen=True)
class Capability:
    capability_id: str
    provider: str
    purpose: str
    operations: tuple[str, ...]
    allowed_data_classes: tuple[str, ...]
    network_access: bool
    estimated_cost_usd: float | None
    runtime_state: str
    read_only: bool = True


_CAPABILITIES = (
    Capability(
        "flybrain.project_context", "local", "Retrieve source-labelled local project context",
        ("retrieve_project_context",), ("public", "internal", "confidential"),
        False, 0.0, "not_ready_until_runtime_adapter_is_wired", True,
    ),
    Capability(
        "web.public_search", "http_research", "Search public HTTPS sources",
        ("browser_search",), ("public",), True, 0.0, "runtime_dependent", True,
    ),
    Capability(
        "web.public_fetch", "http_research", "Fetch public HTTPS pages",
        ("browser_fetch",), ("public",), True, 0.0, "runtime_dependent", True,
    ),
    Capability(
        "model.external_consultation", "modelhub", "Consult explicitly configured external models",
        ("model_consultation",), ("public", "internal"), True, None, "configuration_dependent", True,
    ),
    Capability(
        "browser.interactive", "browser_host", "Perform bounded interactive browser observation",
        ("browser_run_task",), ("public",), True, None, "not_ready_until_verified", False,
    ),
)


class TaskContractError(ValueError):
    """Raised when a task contract is malformed or exceeds its policy bounds."""


def build_task_contract(
    objective: str,
    data_classification: str = "public",
    allowed_providers: list[str] | None = None,
    allow_network: bool = False,
    max_cost_usd: float = 0.0,
    deadline_seconds: int = 60,
) -> dict[str, Any]:
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 4000:
        raise TaskContractError("objective must be a non-empty string of at most 4000 characters")
    if data_classification not in CLASSIFICATIONS:
        raise TaskContractError("data_classification must be public, internal, confidential, or restricted")
    if not isinstance(allow_network, bool):
        raise TaskContractError("allow_network must be boolean")
    if isinstance(max_cost_usd, bool) or not isinstance(max_cost_usd, (int, float)) or not 0 <= max_cost_usd <= 0:
        raise TaskContractError("This planning endpoint is free-only; max_cost_usd must be 0")
    if isinstance(deadline_seconds, bool) or not isinstance(deadline_seconds, int) or not 1 <= deadline_seconds <= 3600:
        raise TaskContractError("deadline_seconds must be an integer from 1 to 3600")
    if allowed_providers is None:
        allowed_providers = ["local"]
    if not isinstance(allowed_providers, list) or len(allowed_providers) > 8:
        raise TaskContractError("allowed_providers must be a list of at most 8 provider names")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 80 for item in allowed_providers):
        raise TaskContractError("Each provider name must be a non-empty string of at most 80 characters")
    providers = sorted(set(item.strip().lower() for item in allowed_providers))
    if data_classification in {"confidential", "restricted"}:
        providers = [provider for provider in providers if provider == "local"]
        allow_network = False
    return {
        "contract_version": "1.0.0",
        "objective": objective.strip(),
        "data_classification": data_classification,
        "allowed_providers": providers,
        "allow_network": allow_network,
        "max_cost_usd": 0.0,
        "deadline_seconds": deadline_seconds,
        "side_effects_allowed": False,
        "requires_human_approval_for_mutations": True,
    }


def capability_registry() -> dict[str, Any]:
    return {
        "status": "completed",
        "registry_version": "1.0.0",
        "execution_enabled": False,
        "capabilities": [asdict(item) for item in _CAPABILITIES],
        "boundary": "Registry metadata and route planning only; provider execution is not implemented by this module.",
    }


def plan_task_route(contract: dict[str, Any], requested_capability: str | None = None) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise TaskContractError("contract must be an object")
    required = {"contract_version", "objective", "data_classification", "allowed_providers",
                "allow_network", "max_cost_usd", "deadline_seconds", "side_effects_allowed"}
    if not required.issubset(contract):
        raise TaskContractError("contract is missing required fields")
    # Re-validate all caller-supplied fields instead of trusting a serialized contract.
    validated = build_task_contract(
        contract["objective"], contract["data_classification"],
        contract["allowed_providers"], contract["allow_network"],
        contract["max_cost_usd"], contract["deadline_seconds"],
    )
    if contract.get("side_effects_allowed") is not False:
        raise TaskContractError("Side effects are disabled by this router")
    if requested_capability is not None and (
        not isinstance(requested_capability, str) or len(requested_capability) > 120
    ):
        raise TaskContractError("requested_capability must be a string of at most 120 characters")
    candidates = []
    for capability in _CAPABILITIES:
        if requested_capability and requested_capability != capability.capability_id:
            continue
        if capability.provider not in validated["allowed_providers"]:
            continue
        if validated["data_classification"] not in capability.allowed_data_classes:
            continue
        if capability.network_access and not validated["allow_network"]:
            continue
        # Unknown provider pricing is not treated as free under a zero-cost budget.
        if capability.estimated_cost_usd is None or capability.estimated_cost_usd > validated["max_cost_usd"]:
            continue
        candidates.append(capability)
    # Prefer local execution; external/network routes are only considered when explicitly allowed.
    candidates.sort(key=lambda item: (item.network_access, item.estimated_cost_usd, item.capability_id))
    if not candidates:
        return {
            "status": "no_eligible_route",
            "contract": validated,
            "routes": [],
            "reason": "No capability satisfies the task's privacy, provider, network, and zero-cost constraints.",
            "execution_started": False,
        }
    return {
        "status": "route_planned",
        "contract": validated,
        "routes": [{
            "capability_id": item.capability_id,
            "provider": item.provider,
            "operations": list(item.operations),
            "runtime_state": item.runtime_state,
            "execution_ready": item.runtime_state == "available",
            "requires_runtime_verification": item.runtime_state != "available",
        } for item in candidates],
        "execution_started": False,
        "reason": "A candidate route was selected; this endpoint does not execute it.",
    }
