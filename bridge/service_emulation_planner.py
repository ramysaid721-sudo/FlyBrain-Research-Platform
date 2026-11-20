"""Deterministic, fail-closed planner for lawful service emulation candidates.

This planner ranks only candidates whose review evidence is already approved.
It does not install, call, or activate services and does not establish legal
clearance. All candidate evidence is treated as caller-supplied input.
"""
from __future__ import annotations

from typing import Any

REQUIRED_CANDIDATE_FIELDS = {
    "candidate_id", "capability", "implementation_type", "review_status",
    "licence_status", "provenance_verified", "terms_status", "security_status",
    "cost_state", "estimated_monthly_cost", "supports_requirements",
    "data_classes", "deployment_modes", "operationally_verified",
}
IMPLEMENTATION_TYPES = {"original", "open_source", "licensed", "hosted_api"}
COST_STATES = {"known_zero", "known_nonzero", "unknown"}
APPROVED_STATES = {"approved"}
DATA_CLASSES = {"public", "internal", "confidential", "restricted"}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _candidate_blockers(candidate: dict[str, Any], requirements: dict[str, Any]) -> list[str]:
    missing = sorted(REQUIRED_CANDIDATE_FIELDS - set(candidate))
    if missing:
        return ["missing candidate fields: " + ", ".join(missing)]
    if not _nonempty(candidate["candidate_id"]) or not _nonempty(candidate["capability"]):
        return ["candidate_id and capability must be non-empty"]
    if candidate["implementation_type"] not in IMPLEMENTATION_TYPES:
        return ["unsupported implementation_type"]
    if candidate["review_status"] != "approved":
        return ["component compliance review is not approved"]
    if candidate["licence_status"] != "approved":
        return ["licence review is not approved"]
    if candidate["terms_status"] != "approved":
        return ["service terms review is not approved"]
    if candidate["security_status"] != "passed":
        return ["security review has not passed"]
    if candidate["provenance_verified"] is not True:
        return ["source provenance is not verified"]
    if candidate["operationally_verified"] is not True:
        return ["operational tests have not passed"]
    if candidate["cost_state"] not in COST_STATES:
        return ["invalid cost_state"]
    if candidate["cost_state"] == "unknown":
        return ["cost is unknown"]
    if candidate["cost_state"] == "known_nonzero" and not requirements.get("allow_paid", False):
        return ["paid candidate is not permitted by this request"]
    if candidate["cost_state"] == "known_zero":
        if candidate["estimated_monthly_cost"] != 0:
            return ["known_zero candidate must have estimated_monthly_cost equal to zero"]
    elif not isinstance(candidate["estimated_monthly_cost"], (int, float)) or candidate["estimated_monthly_cost"] < 0:
        return ["known_nonzero candidate requires a non-negative cost estimate"]
    if not isinstance(candidate["supports_requirements"], list) or not all(
        _nonempty(item) for item in candidate["supports_requirements"]
    ):
        return ["supports_requirements must be a list of non-empty strings"]
    if not isinstance(candidate["data_classes"], list) or not set(candidate["data_classes"]) <= DATA_CLASSES:
        return ["data_classes contains invalid values"]
    if not isinstance(candidate["deployment_modes"], list) or not all(
        _nonempty(item) for item in candidate["deployment_modes"]
    ):
        return ["deployment_modes must be a list of non-empty strings"]
    if not isinstance(candidate["cost_state"], str):
        return ["cost_state must be a string"]

    if candidate["capability"] != requirements["capability"]:
        return ["capability does not match"]
    missing_features = sorted(set(requirements["required_features"]) - set(candidate["supports_requirements"]))
    if missing_features:
        return ["missing required features: " + ", ".join(missing_features)]
    if requirements["data_classification"] not in candidate["data_classes"]:
        return ["candidate does not support the requested data classification"]
    if requirements["deployment_mode"] not in candidate["deployment_modes"]:
        return ["candidate does not support the requested deployment mode"]
    return []


def plan_service_emulation(request: dict[str, Any]) -> dict[str, Any]:
    """Rank eligible candidates; never execute or activate the selected service."""
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    required = {"capability", "required_features", "data_classification", "deployment_mode", "candidates"}
    allowed = required | {"allow_paid"}
    if required - set(request) or set(request) - allowed:
        raise ValueError("request requires capability, required_features, data_classification, deployment_mode, candidates; optional allow_paid")
    if not _nonempty(request["capability"]) or not _nonempty(request["deployment_mode"]):
        raise ValueError("capability and deployment_mode must be non-empty")
    if request["data_classification"] not in DATA_CLASSES:
        raise ValueError("invalid data_classification")
    if not isinstance(request["required_features"], list) or not all(
        _nonempty(item) for item in request["required_features"]
    ):
        raise ValueError("required_features must be a list of non-empty strings")
    if not isinstance(request["candidates"], list):
        raise ValueError("candidates must be a list")
    if "allow_paid" in request and not isinstance(request["allow_paid"], bool):
        raise ValueError("allow_paid must be boolean")

    requirements = dict(request)
    eligible = []
    rejected = []
    for candidate in request["candidates"]:
        if not isinstance(candidate, dict):
            rejected.append({"candidate_id": None, "blockers": ["candidate must be an object"]})
            continue
        blockers = _candidate_blockers(candidate, requirements)
        if blockers:
            rejected.append({"candidate_id": candidate.get("candidate_id"), "blockers": blockers})
            continue
        # Transparent score: feature coverage is a tie-breaker, not a substitute
        # for approval, cost, security, data-classification, or operational gates.
        coverage = len(set(request["required_features"]) & set(candidate["supports_requirements"]))
        eligible.append({
            "candidate_id": candidate["candidate_id"],
            "score": coverage,
            "cost_state": candidate["cost_state"],
            "estimated_monthly_cost": candidate["estimated_monthly_cost"],
            "implementation_type": candidate["implementation_type"],
        })
    eligible.sort(key=lambda item: (
        item["cost_state"] != "known_zero",
        item["estimated_monthly_cost"],
        -item["score"],
        item["candidate_id"],
    ))
    selected = eligible[0] if eligible else None
    return {
        "status": "candidate_selected" if selected else "no_eligible_candidate",
        "selected_candidate": selected,
        "eligible_candidates": eligible,
        "rejected_candidates": rejected,
        "execution_performed": False,
        "activation_performed": False,
        "selection_policy": "Only approved, licensed, provenance-verified, secure, operationally-tested candidates are ranked. Unknown cost fails closed; paid candidates require explicit allow_paid=true.",
        "legal_boundary": "This planner evaluates recorded evidence only; it does not provide legal advice, patent clearance, or a non-infringement determination.",
    }
