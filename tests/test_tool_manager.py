"""Tests for FlyBrain's fail-closed tool lifecycle policy."""
import unittest

from bridge.tool_manager import ToolLifecycleManager, ToolPolicyError


class ToolLifecycleManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = ToolLifecycleManager()

    def test_safe_candidate_is_only_eligible_for_isolated_testing(self):
        result = self.manager.assess("pip-audit", "2.7.3", "official package index")
        self.assertEqual(result["status"], "eligible_for_isolated_testing")
        self.assertFalse(result["installation_authorized"])

    def test_high_impact_tool_is_blocked(self):
        result = self.manager.assess("nmap")
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["requires_human_security_review"])

    def test_unknown_tool_requires_review(self):
        result = self.manager.assess("unknown-package")
        self.assertEqual(result["status"], "review_required")
        self.assertFalse(result["installation_authorized"])

    def test_invalid_name_is_rejected(self):
        with self.assertRaises(ToolPolicyError):
            self.manager.assess("../malicious")

    def test_status_fails_closed_without_worker(self):
        result = self.manager.status()
        self.assertFalse(result["automatic_installation"])
        self.assertFalse(result["automatic_updates"])
        self.assertFalse(result["isolated_worker_ready"])


if __name__ == "__main__":
    unittest.main()
