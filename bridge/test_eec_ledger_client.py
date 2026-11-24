import json
from urllib.request import Request

try:
    from flybrain_os import eec_ledger_client as ledger
except ImportError:
    from bridge import eec_ledger_client as ledger


class FakeResponse:
    status = 200
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size=-1):
        return self.payload[:size]


def configure(monkeypatch):
    monkeypatch.setenv("SUPABASE_EEC_LEDGER_URL", "https://iudimypauqbkyvjuprgp.supabase.co/functions/v1/flybrain-eec-ledger")
    monkeypatch.setenv("FLYBRAIN_EEC_LEDGER_TOKEN", "x" * 64)


def test_ledger_status_reports_configuration_without_exposing_token(monkeypatch):
    configure(monkeypatch)
    status = ledger.ledger_status()
    assert status["configured"] is True
    assert status["environment"] == "staging"
    assert "token" not in json.dumps(status)


def test_persist_plan_strips_raw_objective(monkeypatch):
    configure(monkeypatch)
    captured = {}
    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse({"status": "ok", "result": {"status": "persisted", "task_count": 2}})
    monkeypatch.setattr(ledger, "urlopen", fake_urlopen)
    result = ledger.persist_plan({
        "plan_id": "12233a4b-be9b-5bf5-969c-f1eb278545eb",
        "objective": "private objective must not be transmitted",
        "objective_sha256": "a" * 64,
        "tasks": [],
    })
    assert result["result"]["status"] == "persisted"
    request = captured["request"]
    assert isinstance(request, Request)
    assert b"private objective must not be transmitted" not in request.data
    assert b"objective_sha256" in request.data


def test_plan_status_rejects_invalid_uuid_before_network(monkeypatch):
    configure(monkeypatch)
    def fail_if_called(*args, **kwargs):
        raise AssertionError("network must not be called")
    monkeypatch.setattr(ledger, "urlopen", fail_if_called)
    try:
        ledger.get_plan_status("not-a-uuid")
    except ledger.EECLedgerError:
        pass
    else:
        raise AssertionError("invalid UUID must be rejected")
