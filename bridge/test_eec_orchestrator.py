import unittest
try:
    from flybrain_os.eec_orchestrator import EECPlanError, build_plan, eec_status
except ImportError:
    from bridge.eec_orchestrator import EECPlanError, build_plan, eec_status


class EECOrchestratorTests(unittest.TestCase):
    def test_status_keeps_live_execution_disabled(self):
        status = eec_status()
        self.assertTrue(status["planning"])
        self.assertFalse(status["live_agent_execution"])
        self.assertFalse(status["provider_inference"])
        self.assertEqual(status["zero_cost_policy"], "hard_zero")

    def test_engineering_plan_has_independent_review_lanes(self):
        plan = build_plan("Add a guarded multi-agent execution layer", "engineering")
        roles = {task["role"] for task in plan["tasks"]}
        self.assertTrue({"software_engineer", "security_reviewer", "qa_verifier", "code_reviewer"} <= roles)
        self.assertFalse(plan["policy"]["provider_calls_enabled"])
        self.assertFalse(plan["policy"]["external_data_transfer"])
        self.assertEqual(plan["policy"]["max_spend"], 0)
        self.assertTrue(plan["plan_sha256"])

    def test_research_plan_has_synthesis_dependency(self):
        plan = build_plan("Review recent research", "research")
        synthesis = next(task for task in plan["tasks"] if task["role"] == "synthesizer")
        self.assertEqual(len(synthesis["depends_on"]), 1)
        self.assertEqual(plan["execution_readiness"], "blocked_pending_durable_worker_and_zero_cost_provider_gate")

    def test_parallelism_is_bounded(self):
        with self.assertRaises(EECPlanError):
            build_plan("Test", max_parallel_tasks=5)
        with self.assertRaises(EECPlanError):
            build_plan("Test", max_parallel_tasks=True)

    def test_invalid_inputs_fail_closed(self):
        for args in [("", "general", "internal", 2), ("x" * 8001, "general", "internal", 2),
                     ("Test", "unknown", "internal", 2), ("Test", "general", "private", 2)]:
            with self.assertRaises(EECPlanError):
                build_plan(*args)


if __name__ == "__main__":
    unittest.main()
