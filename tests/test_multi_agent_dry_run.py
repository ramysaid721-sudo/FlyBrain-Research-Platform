import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from multi_agent_dry_run import (  # noqa: E402
    DryRunError,
    DryRunLedger,
    MockOnlyOrchestrator,
    load_sqlite_queue_class,
)

RELEASE_ROOT = ROOT / ".release" / "FlyBrain_Research_Platform_v0.14.0"


class MultiAgentDryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queue_class = load_sqlite_queue_class(RELEASE_ROOT)

    def make_runner(self, root):
        queue = self.queue_class(root / "queue.sqlite3", max_attempts=1)
        ledger = DryRunLedger(root / "ledger.sqlite3")
        return MockOnlyOrchestrator(queue, ledger), queue, ledger

    def test_three_stage_handoff_is_dependency_ordered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner, queue, ledger = self.make_runner(root)
            result = runner.run("Synthetic routing review")
            self.assertEqual(
                [x["role"] for x in result["stages"]],
                ["proposer", "independent_critic", "synthesizer"],
            )
            self.assertEqual([x["state"] for x in result["stages"]], ["completed"] * 3)
            self.assertEqual(result["mode"], "offline_mock_only")
            self.assertEqual(result["network_calls"], 0)
            self.assertEqual(result["provider_credentials_used"], 0)
            self.assertEqual(result["audit_task_count"], 3)
            self.assertEqual(result["audit_event_count"], 9)
            for stage in result["stages"]:
                self.assertEqual(queue.status(stage["task_id"])["state"], "done")

    def test_synthesizer_receives_both_prior_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, _, _ = self.make_runner(Path(tmp))
            result = runner.run("Synthetic independent review")
            proposal_hash = result["stages"][0]["output_sha256"]
            critique_hash = result["stages"][1]["output_sha256"]
            self.assertEqual(result["synthesis"]["proposal_sha256"], proposal_hash)
            self.assertEqual(result["synthesis"]["critique_sha256"], critique_hash)
            self.assertTrue(result["synthesis"]["disagreements_preserved"])

    def test_audit_ledger_stores_hashes_not_raw_task_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner, _, ledger = self.make_runner(root)
            secret_like_text = "synthetic-private-marker-should-not-enter-audit-ledger"
            runner.run(secret_like_text)
            serialized = repr(ledger.task_rows()) + repr(ledger.event_rows())
            self.assertNotIn(secret_like_text, serialized)
            self.assertTrue(all(row[3] for row in ledger.task_rows()))

    def test_empty_and_oversized_tasks_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, _, _ = self.make_runner(Path(tmp))
            with self.assertRaises(DryRunError):
                runner.run("   ")
            with self.assertRaises(DryRunError):
                runner.run("x" * 4001)


if __name__ == "__main__":
    unittest.main()
