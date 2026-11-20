import unittest

from flybrain.providers.gemini_mock import (
    GeminiMockAdapter,
    InvalidMockRequest,
    MOCK_MODEL_ID,
    MockProviderDisabled,
)


class GeminiMockAdapterTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with self.assertRaises(MockProviderDisabled):
            GeminiMockAdapter().review("synthetic public test input")

    def test_rejects_non_boolean_enable_flag(self):
        for value in ("false", "true", 0, 1, None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    GeminiMockAdapter(enabled=value)

    def test_returns_explicit_mock_metadata(self):
        result = GeminiMockAdapter(enabled=True).review("synthetic public test input")
        payload = result.as_dict()
        self.assertEqual(payload["provider"], "google_gemini_mock")
        self.assertEqual(payload["model"], MOCK_MODEL_ID)
        self.assertTrue(payload["mock"])
        self.assertFalse(payload["network_used"])
        self.assertFalse(payload["credential_used"])
        self.assertIn("no model inference occurred", payload["output"])

    def test_rejects_empty_input(self):
        with self.assertRaises(InvalidMockRequest):
            GeminiMockAdapter(enabled=True).review("  ")

    def test_rejects_non_string_input(self):
        with self.assertRaises(InvalidMockRequest):
            GeminiMockAdapter(enabled=True).review(None)

    def test_rejects_oversized_input(self):
        with self.assertRaises(InvalidMockRequest):
            GeminiMockAdapter(enabled=True).review("x" * 4001)


if __name__ == "__main__":
    unittest.main()
