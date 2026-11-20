"""Fail-closed boundary for data sent to external reasoning models.

Only explicitly classified public inputs are eligible. This module does not
scan or sanitize payload contents; callers must classify inputs truthfully and
must never pass secrets or personal data to an external model.
"""
from __future__ import annotations


class ExternalModelDataPolicyError(ValueError):
    """Raised when an input is not eligible for external-model processing."""


def assert_external_model_input_allowed(
    *,
    data_class: str,
    contains_secrets: bool,
    contains_personal_data: bool,
) -> None:
    """Reject anything not explicitly public and affirmatively safe.

    Exact matching is intentional: unknown labels, missing classifications,
    and truthy non-boolean values fail closed.
    """
    if not isinstance(data_class, str) or data_class != "public":
        raise ExternalModelDataPolicyError("external models may process public data only")
    if type(contains_secrets) is not bool or contains_secrets:
        raise ExternalModelDataPolicyError("secret-bearing or unverified inputs are prohibited")
    if type(contains_personal_data) is not bool or contains_personal_data:
        raise ExternalModelDataPolicyError("personal-data-bearing or unverified inputs are prohibited")
