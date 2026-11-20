import json
import os
from unittest.mock import patch

import pytest

from flybrain_os.openrouter_client import (
    OpenRouterBridgeError,
    generate_public_project_answer,
)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


@pytest.fixture
def bridge_environment(monkeypatch):
    monkeypatch.setenv(
        "SUPABASE_OPENROUTER_FUNCTION_URL",
        "https://example.supabase.co/functions/v1/flybrain-openrouter",
    )
    monkeypatch.setenv("FLYBRAIN_OPENROUTER_BRIDGE_TOKEN", "a" * 64)


def success_payload():
    return {
        "status": "completed",
        "provider": "openrouter",
        "requested_model_route": "openrouter/free",
        "served_model": "vendor/model:free",
        "answer": "Public repository analysis",
        "usage": {},
        "external_data_transfer": True,
        "data_scope": "public_project_research",
    }


def test_accepts_only_expected_free_route_response(bridge_environment):
    with patch("flybrain_os.openrouter_client.urlopen", return_value=FakeResponse(success_payload())) as send:
        result = generate_public_project_answer(
            "Explain the public repository", "Public README excerpt"
        )
    assert result["answer"] == "Public repository analysis"
    sent = json.loads(send.call_args.args[0].data.decode("utf-8"))
    assert sent["scope"] == "public_project_research"
    assert sent["data_classification"] == "public"


def test_blocks_email_before_network(bridge_environment):
    with patch("flybrain_os.openrouter_client.urlopen") as send:
        with pytest.raises(ValueError):
            generate_public_project_answer(
                "Contact user@example.com", "Public README excerpt"
            )
    send.assert_not_called()


def test_rejects_non_supabase_endpoint(bridge_environment, monkeypatch):
    monkeypatch.setenv(
        "SUPABASE_OPENROUTER_FUNCTION_URL",
        "https://attacker.example/functions/v1/flybrain-openrouter",
    )
    with pytest.raises(OpenRouterBridgeError):
        generate_public_project_answer("Public question", "Public context")


def test_rejects_unexpected_or_paid_model_route_response(bridge_environment):
    payload = success_payload()
    payload["requested_model_route"] = "vendor/paid-model"
    with patch("flybrain_os.openrouter_client.urlopen", return_value=FakeResponse(payload)):
        with pytest.raises(OpenRouterBridgeError):
            generate_public_project_answer("Public question", "Public context")
