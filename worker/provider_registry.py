"""Quota-aware provider selection for FlyBrain's staging worker plane.

This module is deliberately side-effect free: it selects only among provider
offers whose free capacity and zero-cost status have been explicitly confirmed.
It does not provision resources, read credentials, or execute remote work.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import FrozenSet, Iterable, Optional


@dataclass(frozen=True)
class TaskRequirements:
    runtime: str
    capability: str
    data_class: str = "public"
    max_runtime_seconds: int = 300
    max_cost_usd: float = 0.0
    network_required: bool = False
    region: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.runtime or not self.capability or not self.data_class:
            raise ValueError("runtime, capability, and data_class are required")
        if self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds must be positive")
        if not isfinite(self.max_cost_usd) or self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be finite and non-negative")


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
    network_access: bool = False
    region: Optional[str] = None
    estimated_cost_usd: float = 0.0
    priority: int = 100
    healthy: bool = True
    circuit_open: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("provider name is required")
        if self.max_parallelism < 0 or self.active_jobs < 0:
            raise ValueError("parallelism counters cannot be negative")
        if self.max_runtime_seconds < 0:
            raise ValueError("max_runtime_seconds cannot be negative")
        if not isfinite(self.estimated_cost_usd) or self.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd must be finite and non-negative")


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
        reason = None
        if not offer.enabled:
            reason = "disabled"
        elif not offer.healthy:
            reason = "unhealthy"
        elif offer.circuit_open:
            reason = "circuit_open"
        elif not offer.free_capacity_confirmed:
            reason = "free_capacity_unconfirmed"
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
            item.active_jobs / max(item.max_parallelism, 1),
            item.name,
        ),
    )
    return SelectionResult(provider=chosen, rejected=tuple(rejected))
