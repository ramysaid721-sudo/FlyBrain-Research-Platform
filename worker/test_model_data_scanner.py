"""Tests for conservative external-model payload screening."""
import unittest

from worker.model_data_policy import ExternalModelDataPolicyError
from worker.model_data_scanner import (
    assert_external_model_payload_safe,
    find_sensitive_content,
)


class ModelDataScannerTests(unittest.TestCase):
    def test_clean_public_text_passes(self):
        assert_external_model_payload_safe(
            serialized_payload="Public documentation about a generic algorithm.",
            data_class="public",
            contains_secrets=False,
            contains_personal_data=False,
        )

    def test_private_key_is_detected(self):
        self.assertIn("private_key_pem", find_sensitive_content(
            "-----BEGIN PRIVATE KEY-----\nplaceholder"
        ))

    def test_aws_key_is_detected(self):
        self.assertIn("aws_access_key", find_sensitive_content("AKIA1234567890ABCDEF"))

    def test_github_token_is_detected(self):
        self.assertIn("github_token", find_sensitive_content("ghp_" + "A" * 32))

    def test_github_fine_grained_token_is_detected(self):
        self.assertIn("github_token", find_sensitive_content("github_pat_" + "A" * 24))

    def test_slack_token_is_detected(self):
        self.assertIn("slack_token", find_sensitive_content("xoxb-" + "A" * 20))

    def test_stripe_secret_is_detected(self):
        self.assertIn("stripe_secret", find_sensitive_content("sk_live_" + "A" * 20))

    def test_jwt_is_detected(self):
        self.assertIn("jwt", find_sensitive_content(
            "eyJabcdefgh.eyJabcdefgh.eyJabcdefgh"
        ))

    def test_credential_assignment_is_detected(self):
        self.assertIn("credential_assignment", find_sensitive_content(
            "api_key = 'not-a-real-but-long-secret-value'"
        ))

    def test_email_is_detected(self):
        self.assertIn("email_address", find_sensitive_content("contact person@example.org"))

    def test_phone_like_number_is_detected(self):
        self.assertIn("phone_like_number", find_sensitive_content("Call +1 (202) 555-0198"))

    def test_sensitive_content_rejects_payload(self):
        with self.assertRaises(ExternalModelDataPolicyError):
            assert_external_model_payload_safe(
                serialized_payload="token=ghp_" + "A" * 32,
                data_class="public",
                contains_secrets=False,
                contains_personal_data=False,
            )

    def test_metadata_policy_still_rejects_private_class(self):
        with self.assertRaises(ExternalModelDataPolicyError):
            assert_external_model_payload_safe(
                serialized_payload="Clean text",
                data_class="private",
                contains_secrets=False,
                contains_personal_data=False,
            )

    def test_non_string_payload_fails_closed(self):
        with self.assertRaises(TypeError):
            find_sensitive_content(None)


    def test_json_quoted_credential_assignment_is_detected(self):
        payload = '{"api_key":"synthetic-secret-value"}'
        self.assertIn("credential_assignment", find_sensitive_content(payload))


if __name__ == "__main__":
    unittest.main()
