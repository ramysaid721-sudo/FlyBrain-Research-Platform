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


def test_http_fetch_extracts_content_and_links(monkeypatch):
    from flybrain_os import browser_use_adapter as adapter
    html = '<html><head><title>Research Page</title><meta name="description" content="A useful source"></head><body><h1>Finding</h1><p>Evidence from a public page.</p><a href="https://example.org/source">Primary source</a></body></html>'
    monkeypatch.setattr(adapter, "_http_get", lambda *a, **k: ("https://example.com/page", "text/html; charset=utf-8", html))
    monkeypatch.setattr(adapter, "_validate_url", lambda url: url)
    result = adapter.run_browser_fetch("https://example.com/page")
    assert result["status"] == "completed"
    assert result["title"] == "Research Page"
    assert "Evidence from a public page" in result["content"]
    assert result["links"][0]["url"] == "https://example.org/source"


def test_public_web_search_extracts_results(monkeypatch):
    from flybrain_os import browser_use_adapter as adapter
    html = '<a class="result__a" href="https://example.org/paper">Research paper</a><a class="result__snippet">A peer reviewed result.</a>'
    monkeypatch.setattr(adapter, "_http_get", lambda *a, **k: ("https://html.duckduckgo.com/html/", "text/html", html))
    monkeypatch.setattr(adapter, "_validate_url", lambda url: url)
    result = adapter.run_browser_search("test query", 3)
    assert result["status"] == "completed"
    assert result["results"][0]["title"] == "Research paper"
    assert result["results"][0]["snippet"] == "A peer reviewed result."
    assert result["results"][0]["url"] == "https://example.org/paper"


def test_research_returns_exact_source_urls(monkeypatch):
    from flybrain_os import browser_use_adapter as adapter
    monkeypatch.setattr(adapter, "run_browser_search", lambda q, max_results: {
        "status": "completed", "results": [{"title": "Paper", "url": "https://example.org/paper", "snippet": "Abstract", "source_domain": "example.org"}],
        "search_engine": "test"
    })
    monkeypatch.setattr(adapter, "run_browser_fetch", lambda url, output_format, include_links: {
        "status": "completed", "url": url, "title": "Paper title", "content": "Source evidence"
    })
    result = adapter.run_browser_research("research question", 2)
    assert result["sources"][0]["url"] == "https://example.org/paper"
    assert result["sources"][0]["page_excerpt"] == "Source evidence"


def test_dns_private_address_is_blocked(monkeypatch):
    import socket
    from flybrain_os import browser_use_adapter as adapter
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))])
    with pytest.raises(ValueError):
        adapter._validate_url("https://public-looking.example/")


def test_status_separates_http_research_from_interactive_browser(monkeypatch):
    from flybrain_os import browser_use_adapter as adapter
    monkeypatch.setenv("BROWSER_USE_PROVIDER", "ollama")
    monkeypatch.setattr(adapter, "_make_llm", lambda: None)
    monkeypatch.setattr(adapter, "urlopen", None, raising=False)
    monkeypatch.setitem(sys.modules, "browser_use", None)
    result = adapter.browser_use_status()
    assert result["web_search_ready"] is True
    assert result["web_fetch_ready"] is True
    assert result["interactive_browser_ready"] is False



def test_http_get_decodes_declared_legacy_charset(monkeypatch):
    from flybrain_os import browser_use_adapter as adapter

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/plain; charset=iso-8859-1"}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return "https://example.com/text"
        def read(self, limit): return "caf\xe9".encode("iso-8859-1")

    class FakeOpener:
        def open(self, request, timeout): return FakeResponse()

    monkeypatch.setattr(adapter, "_validate_url", lambda value: value)
    monkeypatch.setattr(adapter, "build_opener", lambda *args: FakeOpener())
    final_url, content_type, body = adapter._http_get("https://example.com/text")
    assert final_url == "https://example.com/text"
    assert "iso-8859-1" in content_type
    assert body == "caf\xe9"
