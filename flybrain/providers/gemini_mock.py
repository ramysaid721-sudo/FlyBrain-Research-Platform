"""Deterministic, network-free Gemini-shaped mock for FlyBrain staging tests.

This module is deliberately NOT a Google Gemini client:
- it imports no HTTP/network libraries;
- it never reads environment variables or Supabase Vault;
- it accepts no API key and has no transport implementation;
- it returns synthetic output only.
"""
from dataclasses import dataclass
from typing import Any


class MockProviderDisabled(RuntimeError):
    """Raised when the local mock is not explicitly enabled."""


class InvalidMockRequest(ValueError):
    """Raised when a mock request is outside the bounded test contract."""


MOCK_MODEL_ID = "mock-gemini-review-v1"
MAX_INPUT_CHARS = 4_000


@dataclass(frozen=True)
class MockResponse:
    provider: str
    model: str
    output: str
    mock: bool = True
    network_used: bool = False
    credential_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "output": self.output,
            "mock": self.mock,
            "network_used": self.network_used,
            "credential_used": self.credential_used,
        }


class GeminiMockAdapter:
    """A deterministic local substitute; it cannot contact Google."""

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled

    def review(self, text: str) -> MockResponse:
        if not self._enabled:
            raise MockProviderDisabled("Gemini mock is disabled; no provider call was made.")
        if not isinstance(text, str) or not text.strip():
            raise InvalidMockRequest("text must be a non-empty string")
        if len(text) > MAX_INPUT_CHARS:
            raise InvalidMockRequest(f"text exceeds {MAX_INPUT_CHARS} characters")

        # Deliberately do not echo user input into logs or claim an AI analysis.
        return MockResponse(
            provider="google_gemini_mock",
            model=MOCK_MODEL_ID,
            output="MOCK_OK: synthetic review response; no model inference occurred.",
        )
