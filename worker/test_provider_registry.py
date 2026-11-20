"""Unit tests for the fail-closed FACO provider selector."""
import unittest
from math import inf, nan

from worker.provider_registry import (
    ProviderOffer,
    TaskRequirements,
    select_provider,
)


def offer(name="alpha", **overrides):
    values = {
        "name": name,
        "enabled": True,
        "free_capacity_confirmed": True,
        "max_parallelism": 2,
        "active_jobs": 0,
        "max_runtime_seconds": 600,
        "supported_runtimes": frozenset({"python3.12"}),
        "capabilities": frozenset({"pytest", "cpu"}),
        "allowed_data_classes": frozenset({"public", "internal"}),
        "estimated_cost_usd": 0.0,
        "network_access": True,
        "region": "sin1",
        "priority": 10,
        "healthy": True,
        "circuit_open": False,
    }
    values.update(overrides)
    return ProviderOffer(**values)


class ProviderRegistryTests(unittest.TestCase):
    def setUp(self):
        self.requirements = TaskRequirements(
            runtime="python3.12",
            capability="pytest",
            data_class="internal",
            max_runtime_seconds=300,
            max_cost_usd=0.0,
            network_required=True,
            region="sin1",
        )

    def test_selects_eligible_provider(self):
        result = select_provider(self.requirements, [offer()])
        self.assertTrue(result.selected)
        self.assertEqual(result.provider.name, "alpha")

    def test_unknown_free_capacity_fails_closed(self):
        result = select_provider(
            self.requirements,
            [offer(free_capacity_confirmed=False)],
        )
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "free_capacity_unconfirmed"), result.rejected)

    def test_nonzero_cost_exceeds_zero_ceiling(self):
        result = select_provider(
            self.requirements,
            [offer(estimated_cost_usd=0.0001)],
        )
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "cost_ceiling_exceeded"), result.rejected)

    def test_open_circuit_is_rejected(self):
        result = select_provider(self.requirements, [offer(circuit_open=True)])
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "circuit_open"), result.rejected)

    def test_unhealthy_provider_is_rejected(self):
        result = select_provider(self.requirements, [offer(healthy=False)])
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "unhealthy"), result.rejected)

    def test_exhausted_capacity_is_rejected(self):
        result = select_provider(
            self.requirements,
            [offer(max_parallelism=1, active_jobs=1)],
        )
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "capacity_exhausted"), result.rejected)

    def test_runtime_and_data_policy_are_enforced(self):
        result = select_provider(
            self.requirements,
            [offer(supported_runtimes=frozenset({"python3.14"}))],
        )
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "runtime_unsupported"), result.rejected)

        result = select_provider(
            self.requirements,
            [offer(allowed_data_classes=frozenset({"public"}))],
        )
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "data_class_not_allowed"), result.rejected)

    def test_network_and_region_requirements_are_enforced(self):
        result = select_provider(
            self.requirements,
            [offer(network_access=False)],
        )
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "network_unavailable"), result.rejected)

        result = select_provider(
            self.requirements,
            [offer(region="fra1")],
        )
        self.assertFalse(result.selected)
        self.assertIn(("alpha", "region_mismatch"), result.rejected)

    def test_priority_then_utilization_then_name_is_deterministic(self):
        chosen = select_provider(
            self.requirements,
            [
                offer("zeta", priority=10, active_jobs=1),
                offer("beta", priority=10, active_jobs=0),
                offer("alpha", priority=5, active_jobs=1),
            ],
        )
        self.assertEqual(chosen.provider.name, "alpha")

        tie = select_provider(
            self.requirements,
            [offer("zeta"), offer("beta")],
        )
        self.assertEqual(tie.provider.name, "beta")

    def test_no_offers_returns_no_selection(self):
        result = select_provider(self.requirements, [])
        self.assertIsNone(result.provider)
        self.assertFalse(result.selected)


    def test_invalid_task_costs_and_runtime_are_rejected(self):
        for invalid_cost in (-0.01, nan, inf):
            with self.subTest(cost=invalid_cost):
                with self.assertRaises(ValueError):
                    TaskRequirements(
                        runtime="python3.12",
                        capability="pytest",
                        max_cost_usd=invalid_cost,
                    )
        with self.assertRaises(ValueError):
            TaskRequirements(runtime="python3.12", capability="pytest", max_runtime_seconds=0)

    def test_invalid_provider_costs_and_capacity_are_rejected(self):
        for invalid_cost in (-0.01, nan, inf):
            with self.subTest(cost=invalid_cost):
                with self.assertRaises(ValueError):
                    offer(estimated_cost_usd=invalid_cost)
        with self.assertRaises(ValueError):
            offer(max_parallelism=-1)


    def test_boolean_fields_require_real_booleans(self):
        for field in ("enabled", "free_capacity_confirmed", "healthy", "circuit_open", "network_access"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    offer(**{field: 1})

        with self.assertRaises(ValueError):
            TaskRequirements(runtime="python3.12", capability="pytest", network_required=1)

    def test_integer_limits_reject_booleans_zero_and_inconsistent_counts(self):
        for changes in (
            {"max_parallelism": 0},
            {"max_parallelism": True},
            {"active_jobs": True},
            {"max_runtime_seconds": 0},
            {"active_jobs": 3, "max_parallelism": 2},
            {"priority": -1},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    offer(**changes)

    def test_malformed_cost_types_and_capability_sets_are_rejected(self):
        for cost in ("0", True, None):
            with self.subTest(cost=cost):
                with self.assertRaises(ValueError):
                    offer(estimated_cost_usd=cost)
        for capabilities in ({"pytest"}, frozenset({"", "cpu"}), ["pytest"]):
            with self.subTest(capabilities=capabilities):
                with self.assertRaises(ValueError):
                    offer(capabilities=capabilities)

    def test_unsupported_capability_and_runtime_limit_are_rejected(self):
        result = select_provider(self.requirements, [offer(capabilities=frozenset({"cpu"}))])
        self.assertIn(("alpha", "capability_unsupported"), result.rejected)
        result = select_provider(self.requirements, [offer(max_runtime_seconds=120)])
        self.assertIn(("alpha", "runtime_limit_too_short"), result.rejected)

    def test_non_provider_offer_is_rejected_as_invalid_input(self):
        with self.assertRaises(TypeError):
            select_provider(self.requirements, [object()])


if __name__ == "__main__":
    unittest.main()
