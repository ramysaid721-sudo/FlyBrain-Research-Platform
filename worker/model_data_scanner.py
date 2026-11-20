"""Conservative content screening before external-model inference.

This is a defense-in-depth heuristic, not a complete secret or PII detector.
Callers must serialize the exact payload that will be sent and still enforce
trusted provenance/classification. Unknown inputs must fail closed.
"""
from __future__ import annotations

import re

from .model_data_policy import (
    ExternalModelDataPolicyError,
    assert_external_model_input_allowed,
)

# Patterns intentionally return rule identifiers only; matched values are
# never copied into logs or exception messages.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_pem", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe_secret", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{12,}\b")),
    ("openai_style_secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("credential_assignment", re.compile(
        r"""(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*["']?[^\s"'\x60]{8,}"""
    )),
    ("email_address", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    ("phone_like_number", re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")),
)


def find_sensitive_content(text: str) -> tuple[str, ...]:
    """Return unique rule IDs detected in text; never return matched values."""
    if not isinstance(text, str):
        raise TypeError("payload text must be a string")
    return tuple(rule for rule, pattern in _RULES if pattern.search(text))


def assert_external_model_payload_safe(
    *,
    serialized_payload: str,
    data_class: str,
    contains_secrets: bool,
    contains_personal_data: bool,
) -> None:
    """Apply explicit metadata policy and conservative content heuristics."""
    assert_external_model_input_allowed(
        data_class=data_class,
        contains_secrets=contains_secrets,
        contains_personal_data=contains_personal_data,
    )
    findings = find_sensitive_content(serialized_payload)
    if findings:
        raise ExternalModelDataPolicyError(
            "payload rejected by content screening: " + ", ".join(findings)
        )
