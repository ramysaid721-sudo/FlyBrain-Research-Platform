"""Quota-aware provider selection for FlyBrain's staging worker plane.

This module is deliberately side-effect free: it selects only among provider
offers whose free capacity and zero-cost status have been explicitly confirmed.
It does not provision resources, read credentials, or execute remote work.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import FrozenSet, Iterable, Optional


def _require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _require_bool(value: object, field: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")


def _require_int(value: object, field: str, *, minimum: int) -> None:
    # bool is an int subclass, so use an exact type check.
    if type(value) is not int or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")


def _require_cost(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{field} must be a finite non-negative number")


def _require_string_set(value: object, field: str) -> None:
    if not isinstance(value, frozenset) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{field} must be a frozenset of non-empty strings")


@dataclass(frozen=True)
class TaskRequirements:
    runtime: str
    capability: str
    data_class: str = "public"
    max_runtime_seconds: int = 300
    max_cost_usd: float = 0.0
    network_required: bool = False
    region: Optional[str] = None
    max_quota_evidence_age_seconds: int = 120

    def __post_init__(self) -> None:
        _require_text(self.runtime, "runtime")
        _require_text(self.capability, "capability")
        _require_text(self.data_class, "data_class")
        _require_int(self.max_runtime_seconds, "max_runtime_seconds", minimum=1)
        _require_cost(self.max_cost_usd, "max_cost_usd")
        _require_bool(self.network_required, "network_required")
        if self.region is not None:
            _require_text(self.region, "region")
        _require_int(self.max_quota_evidence_age_seconds, "max_quota_evidence_age_seconds", minimum=1)


@dataclass(frozen=True)
class ProviderOffer:
    name: str
    enabled: bool
    free_capacity_confirmed: bool
    max_parallelism: int
    active_jobs: int
    max_runtime_seconds: int
    supported_runtimes: FrozenSet[str]
    capabilities: FrozenSet[str]
    allowed_data_classes: FrozenSet[str]
    estimated_cost_usd: float
    network_access: bool = False
    region: Optional[str] = None
    priority: int = 100
    healthy: bool = True
    circuit_open: bool = False
    quota_evidence_age_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        _require_text(self.name, "name")
        for field in (
            "enabled",
            "free_capacity_confirmed",
            "network_access",
            "healthy",
            "circuit_open",
        ):
            _require_bool(getattr(self, field), field)
        _require_int(self.max_parallelism, "max_parallelism", minimum=1)
        _require_int(self.active_jobs, "active_jobs", minimum=0)
        if self.active_jobs > self.max_parallelism:
            raise ValueError("active_jobs cannot exceed max_parallelism")
        _require_int(self.max_runtime_seconds, "max_runtime_seconds", minimum=1)
        _require_int(self.priority, "priority", minimum=0)
        _require_string_set(self.supported_runtimes, "supported_runtimes")
        _require_string_set(self.capabilities, "capabilities")
        _require_string_set(self.allowed_data_classes, "allowed_data_classes")
        _require_cost(self.estimated_cost_usd, "estimated_cost_usd")
        if self.region is not None:
            _require_text(self.region, "region")
        if self.quota_evidence_age_seconds is not None:
            _require_int(self.quota_evidence_age_seconds, "quota_evidence_age_seconds", minimum=0)


@dataclass(frozen=True)
class SelectionResult:
    provider: Optional[ProviderOffer]
    rejected: tuple[tuple[str, str], ...]

    @property
    def selected(self) -> bool:
        return self.provider is not None


def select_provider(
    requirements: TaskRequirements,
    offers: Iterable[ProviderOffer],
) -> SelectionResult:
    """Choose the best eligible provider, failing closed when none is safe.

    The selector never treats an unknown quota as free capacity. Offers must
    explicitly attest both zero estimated cost and confirmed free capacity.
    """
    eligible: list[ProviderOffer] = []
    rejected: list[tuple[str, str]] = []

    for offer in offers:
        if not isinstance(offer, ProviderOffer):
            raise TypeError("offers must contain only ProviderOffer instances")
        reason = None
        if not offer.enabled:
            reason = "disabled"
        elif not offer.healthy:
            reason = "unhealthy"
        elif offer.circuit_open:
            reason = "circuit_open"
        elif not offer.free_capacity_confirmed:
            reason = "free_capacity_unconfirmed"
        elif offer.quota_evidence_age_seconds is None:
            reason = "quota_evidence_missing"
        elif offer.quota_evidence_age_seconds > requirements.max_quota_evidence_age_seconds:
            reason = "quota_evidence_stale"
        elif offer.estimated_cost_usd != 0:
            # FACO is currently free-only: a nonzero quote is rejected even
            # when a caller supplies a positive task budget.
            reason = "nonzero_cost"
        elif offer.estimated_cost_usd > requirements.max_cost_usd:
            reason = "cost_ceiling_exceeded"
        elif offer.active_jobs >= offer.max_parallelism:
            reason = "capacity_exhausted"
        elif requirements.runtime not in offer.supported_runtimes:
            reason = "runtime_unsupported"
        elif requirements.capability not in offer.capabilities:
            reason = "capability_unsupported"
        elif requirements.data_class not in offer.allowed_data_classes:
            reason = "data_class_not_allowed"
        elif requirements.network_required and not offer.network_access:
            reason = "network_unavailable"
        elif offer.max_runtime_seconds < requirements.max_runtime_seconds:
            reason = "runtime_limit_too_short"
        elif requirements.region and offer.region != requirements.region:
            reason = "region_mismatch"

        if reason:
            rejected.append((offer.name, reason))
        else:
            eligible.append(offer)

    if not eligible:
        return SelectionResult(provider=None, rejected=tuple(rejected))

    # Prefer configured priority, then lower utilization, then stable name.
    chosen = min(
        eligible,
        key=lambda item: (
            item.priority,
            item.active_jobs / item.max_parallelism,
            item.name,
        ),
    )
    return SelectionResult(provider=chosen, rejected=tuple(rejected))
