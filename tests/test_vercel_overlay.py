import unittest
from pathlib import Path


class VercelOverlayTests(unittest.TestCase):
    def test_eec_module_is_copied_into_serverless_runtime(self):
        root = Path(__file__).resolve().parents[1]
        entrypoint = (root / "api" / "index.py").read_text(encoding="utf-8")
        module = root / "bridge" / "eec_orchestrator.py"
        self.assertTrue(module.is_file())
        self.assertIn('"eec_orchestrator.py"', entrypoint)


if __name__ == "__main__":
    unittest.main()
