"""Tests for the external reasoning-model data boundary."""
import unittest

from worker.model_data_policy import (
    ExternalModelDataPolicyError,
    assert_external_model_input_allowed,
)


class ExternalModelDataPolicyTests(unittest.TestCase):
    def test_explicit_public_non_sensitive_input_is_allowed(self):
        self.assertIsNone(assert_external_model_input_allowed(
            data_class="public",
            contains_secrets=False,
            contains_personal_data=False,
        ))

    def test_internal_private_and_confidential_classes_are_rejected(self):
        for data_class in ("internal", "private", "confidential", "restricted"):
            with self.subTest(data_class=data_class):
                with self.assertRaises(ExternalModelDataPolicyError):
                    assert_external_model_input_allowed(
                        data_class=data_class,
                        contains_secrets=False,
                        contains_personal_data=False,
                    )

    def test_unknown_or_missing_classification_fails_closed(self):
        for data_class in (None, "", "PUBLIC", "public "):
            with self.subTest(data_class=data_class):
                with self.assertRaises(ExternalModelDataPolicyError):
                    assert_external_model_input_allowed(
                        data_class=data_class,
                        contains_secrets=False,
                        contains_personal_data=False,
                    )

    def test_secrets_are_rejected(self):
        with self.assertRaises(ExternalModelDataPolicyError):
            assert_external_model_input_allowed(
                data_class="public",
                contains_secrets=True,
                contains_personal_data=False,
            )

    def test_personal_data_is_rejected(self):
        with self.assertRaises(ExternalModelDataPolicyError):
            assert_external_model_input_allowed(
                data_class="public",
                contains_secrets=False,
                contains_personal_data=True,
            )

    def test_unverified_sensitivity_flags_fail_closed(self):
        for field, value in (
            ("contains_secrets", None),
            ("contains_secrets", 0),
            ("contains_personal_data", None),
            ("contains_personal_data", "false"),
        ):
            with self.subTest(field=field, value=value):
                args = {
                    "data_class": "public",
                    "contains_secrets": False,
                    "contains_personal_data": False,
                }
                args[field] = value
                with self.assertRaises(ExternalModelDataPolicyError):
                    assert_external_model_input_allowed(**args)


if __name__ == "__main__":
    unittest.main()
