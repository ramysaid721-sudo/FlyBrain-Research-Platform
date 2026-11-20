import io
import json
from types import SimpleNamespace
import pytest
from flybrain_os.chat_api import FlyBrainChatApp

def invoke(app, method="GET", path="/health", payload=None, token=None):
    raw = b"" if payload is None else json.dumps(payload).encode()
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)),
               "wsgi.input": io.BytesIO(raw), "HTTP_AUTHORIZATION": f"Bearer {token}" if token else ""}
    captured = {}
    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)
    body = b"".join(app(environ, start_response))
    return captured, json.loads(body)

def test_health_is_public_and_identifies_service(tmp_path):
    app = FlyBrainChatApp("x" * 40, tmp_path / "ledger.sqlite3")
    response, body = invoke(app)
    assert response["status"] == "200 OK"
    assert body["service"] == "flybrain-chat-bridge"

def test_ask_requires_bearer_token(tmp_path):
    app = FlyBrainChatApp("x" * 40, tmp_path / "ledger.sqlite3")
    response, body = invoke(app, "POST", "/v1/ask", {"question": "hello"})
    assert response["status"] == "401 Unauthorized"
    assert body["error"] == "unauthorized"

def test_ask_validates_question_before_provider_lookup(tmp_path):
    token = "x" * 40
    app = FlyBrainChatApp(token, tmp_path / "ledger.sqlite3")
    response, body = invoke(app, "POST", "/v1/ask", {"question": "  "}, token)
    assert response["status"] == "400 Bad Request"
    assert body["error"].startswith("question must be")

def test_ask_returns_clear_no_provider_state(tmp_path, monkeypatch):
    token = "x" * 40
    monkeypatch.setattr("flybrain_os.chat_api.ModelConsultation.consult", lambda *a, **k: {
        "status": "no_providers_configured", "results": [], "note": "none"})
    app = FlyBrainChatApp(token, tmp_path / "ledger.sqlite3")
    response, body = invoke(app, "POST", "/v1/ask", {"question": "What is a connectome?"}, token)
    assert response["status"] == "200 OK"
    assert body["status"] == "context_only"
    assert body["external_data_transfer"] is False
    assert "metadata only" in body["scientific_scope"]

def test_ask_returns_gateway_error_when_all_providers_fail(tmp_path, monkeypatch):
    token = "x" * 40
    monkeypatch.setattr("flybrain_os.chat_api.ModelConsultation.consult", lambda *a, **k: {
        "status": "all_providers_failed", "results": [{"status": "error"}]})
    app = FlyBrainChatApp(token, tmp_path / "ledger.sqlite3")
    response, body = invoke(app, "POST", "/v1/ask", {"question": "What is a connectome?"}, token)
    assert response["status"] == "502 Bad Gateway"
    assert body["status"] == "all_providers_failed"


def test_ask_requires_public_attestation_when_provider_is_configured(tmp_path, monkeypatch):
    token = "x" * 40
    called = []
    monkeypatch.setattr(
        "flybrain_os.chat_api.model_hub.discover_providers",
        lambda: [SimpleNamespace(provider_id="test", model="test-model")],
    )
    monkeypatch.setattr(
        "flybrain_os.chat_api.ModelConsultation.consult",
        lambda *args, **kwargs: called.append((args, kwargs)),
    )
    app = FlyBrainChatApp(token, tmp_path / "ledger.sqlite3")
    response, body = invoke(app, "POST", "/v1/ask", {"question": "public question"}, token)
    assert response["status"] == "400 Bad Request"
    assert body["error"] == "public_data_attestation_required"
    assert called == []


def test_guard_scans_exact_serialized_payload_before_network(tmp_path, monkeypatch):
    import flybrain_os.chat_api as chat_api
    network_calls = []

    def fake_post(provider, prompt, *, timeout, opener):
        request = SimpleNamespace(data=b'{"model":"test-model","input":"public information"}')
        return opener(request, timeout=timeout)

    monkeypatch.setattr(chat_api.model_hub, "_post_chat", fake_post)
    monkeypatch.setattr(
        chat_api.model_hub.urllib.request,
        "urlopen",
        lambda request, timeout: network_calls.append(request) or "sent",
    )
    provider = SimpleNamespace(provider_id="test", model="test-model")
    result = chat_api._guarded_post_chat(
        provider, "public information", timeout=5,
        data_class="public", contains_secrets=False, contains_personal_data=False,
    )
    assert result == "sent"
    assert len(network_calls) == 1


def test_guard_blocks_sensitive_payload_before_network(monkeypatch):
    import flybrain_os.chat_api as chat_api
    network_calls = []

    def fake_post(provider, prompt, *, timeout, opener):
        request = SimpleNamespace(data=b'{"api_key":"synthetic-secret-value"}')
        return opener(request, timeout=timeout)

    monkeypatch.setattr(chat_api.model_hub, "_post_chat", fake_post)
    monkeypatch.setattr(
        chat_api.model_hub.urllib.request,
        "urlopen",
        lambda request, timeout: network_calls.append(request) or "sent",
    )
    provider = SimpleNamespace(provider_id="test", model="test-model")
    with pytest.raises(ValueError):
        chat_api._guarded_post_chat(
            provider, "public information", timeout=5,
            data_class="public", contains_secrets=False, contains_personal_data=False,
        )
    assert network_calls == []
