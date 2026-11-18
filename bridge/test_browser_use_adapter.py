import sys
import types
import pytest
from flybrain_os.browser_use_adapter import _validate_url, browser_use_status, run_browser_task

def test_rejects_non_https_and_local_targets():
    with pytest.raises(ValueError):
        _validate_url("http://example.com")
    with pytest.raises(ValueError):
        _validate_url("https://localhost/admin")
    with pytest.raises(ValueError):
        _validate_url("https://127.0.0.1/")

def test_side_effects_require_explicit_approval(monkeypatch):
    monkeypatch.setenv("BROWSER_USE_PROVIDER", "ollama")
    result = run_browser_task("https://example.com", "Submit the contact form")
    assert result["status"] == "approval_required"

def test_unsupported_provider_is_not_ready(monkeypatch):
    monkeypatch.setenv("BROWSER_USE_PROVIDER", "unsupported")
    assert browser_use_status()["ready"] is False

def test_completed_task_uses_browser_use_api(monkeypatch):
    monkeypatch.setenv("BROWSER_USE_PROVIDER", "ollama")
    fake = types.ModuleType("browser_use")
    class FakeBrowser:
        def __init__(self, *args, **kwargs): pass
    class FakeResult:
        error = None
        def final_result(self): return '{"title":"Example Domain"}'
        def number_of_steps(self): return 2
    class FakeAgent:
        def __init__(self, **kwargs): pass
        def run_sync(self, max_steps):
            assert max_steps == 3
            return FakeResult()
    class FakeChatOpenAI:
        def __init__(self, **kwargs): pass
    fake.Agent, fake.Browser, fake.ChatOpenAI = FakeAgent, FakeBrowser, FakeChatOpenAI
    fake.__version__ = "1.0.0"
    monkeypatch.setitem(sys.modules, "browser_use", fake)
    monkeypatch.setattr("flybrain_os.browser_use_adapter.browser_use_status", lambda: {"installed": True, "version": "1.0.0", "provider": "ollama", "ready": True, "browser_mode": "local Chromium"})
    result = run_browser_task("https://example.com", "Read the page title", max_steps=3)
    assert result["status"] == "completed"
    assert result["steps"] == 2
    assert "Example Domain" in result["result"]
