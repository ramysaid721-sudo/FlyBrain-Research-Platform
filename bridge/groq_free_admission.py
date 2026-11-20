"""Fail-closed admission policy for experimental Groq staging calls.

This module deliberately does not perform network I/O. A caller must provide
fresh, provider-derived pricing and quota evidence before any future transport
layer can be enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    reason: str


def evaluate_groq_admission(
    evidence: Mapping[str, Any] | None,
    *,
    requested_model: str,
    allowlisted_models: set[str] | frozenset[str],
    now_epoch: float,
    max_evidence_age_seconds: int = 120,
) -> AdmissionDecision:
    """Allow only an explicitly allowlisted model with fresh, zero-priced evidence.

    Missing, malformed, stale, non-zero, or mismatched evidence is rejected.
    The function is intentionally pure so its rejection behavior is testable
    without credentials, network access, or billable inference requests.
    """
    if not isinstance(requested_model, str) or not requested_model:
        return AdmissionDecision(False, "invalid_model")
    if requested_model not in allowlisted_models:
        return AdmissionDecision(False, "model_not_allowlisted")
    if not isinstance(evidence, Mapping):
        return AdmissionDecision(False, "pricing_quota_evidence_missing")

    required = {
        "model_id",
        "captured_at",
        "source",
        "input_cost_per_million",
        "output_cost_per_million",
        "remaining_requests",
        "remaining_tokens",
        "free_quota_confirmed",
    }
    if not required.issubset(evidence.keys()):
        return AdmissionDecision(False, "pricing_quota_evidence_incomplete")
    if evidence.get("model_id") != requested_model:
        return AdmissionDecision(False, "evidence_model_mismatch")
    source = evidence.get("source")
    if not isinstance(source, str) or not source.startswith("https://"):
        return AdmissionDecision(False, "untrusted_evidence_source")

    try:
        captured_at = float(evidence["captured_at"])
        age = float(now_epoch) - captured_at
        input_cost = float(evidence["input_cost_per_million"])
        output_cost = float(evidence["output_cost_per_million"])
        remaining_requests = int(evidence["remaining_requests"])
        remaining_tokens = int(evidence["remaining_tokens"])
    except (TypeError, ValueError, OverflowError):
        return AdmissionDecision(False, "malformed_pricing_quota_evidence")

    if age < 0 or age > max_evidence_age_seconds:
        return AdmissionDecision(False, "pricing_quota_evidence_stale")
    if input_cost != 0 or output_cost != 0:
        return AdmissionDecision(False, "nonzero_or_unknown_model_price")
    if remaining_requests <= 0 or remaining_tokens <= 0:
        return AdmissionDecision(False, "free_quota_exhausted_or_unknown")
    if evidence.get("free_quota_confirmed") is not True:
        return AdmissionDecision(False, "free_quota_not_confirmed")

    return AdmissionDecision(True, "zero_cost_and_fresh_quota_verified")
