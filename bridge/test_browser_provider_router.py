from bridge import browser_use_adapter as adapter


def test_provider_status_defaults_to_http_and_disables_remote_providers(monkeypatch):
    for key in (
        "FLYBRAIN_WEB_FETCH_PROVIDER",
        "FLYBRAIN_BROWSER_WORKER_URL",
        "FLYBRAIN_BROWSER_API_TOKEN",
        "FLYBRAIN_BROWSER_RUN_ALLOW_USAGE",
        "BROWSERLESS_TOKEN",
        "BROWSERLESS_ALLOW_USAGE",
    ):
        monkeypatch.delenv(key, raising=False)

    status = adapter.browser_provider_status()
    assert status["strategy"] == "auto"
    assert status["http"]["ready"] is True
    assert status["cloudflare"]["configured"] is False
    assert status["browserless"]["configured"] is False
    assert status["playwright"]["ready"] is False


def test_auto_router_returns_good_http_content_without_spending_browser_quota(monkeypatch):
    monkeypatch.setenv("FLYBRAIN_WEB_FETCH_PROVIDER", "auto")
    monkeypatch.setattr(adapter, "_validate_url", lambda value: value)
    monkeypatch.setattr(adapter, "_run_http_browser_fetch", lambda *args: {
        "status": "completed", "provider": "http", "content": "Useful static content " * 30
    })
    monkeypatch.setattr(adapter, "cloudflare_browser_status", lambda: {"configured": True})
    monkeypatch.setattr(adapter, "browserless_status", lambda: {"configured": True})
    monkeypatch.setattr(adapter, "run_cloudflare_playwright_fetch", lambda url: (_ for _ in ()).throw(
        AssertionError("Cloudflare should not be called for sufficient HTTP content")
    ))
    monkeypatch.setattr(adapter, "run_browserless_fetch", lambda *args: (_ for _ in ()).throw(
        AssertionError("Browserless should not be called for sufficient HTTP content")
    ))

    result = adapter.run_browser_fetch("https://example.com")
    assert result["provider"] == "http"


def test_auto_router_falls_back_cloudflare_then_browserless(monkeypatch):
    monkeypatch.setenv("FLYBRAIN_WEB_FETCH_PROVIDER", "auto")
    monkeypatch.setattr(adapter, "_validate_url", lambda value: value)
    monkeypatch.setattr(adapter, "_run_http_browser_fetch", lambda *args: {
        "status": "completed", "provider": "http", "content": "Loading JavaScript application"
    })
    monkeypatch.setattr(adapter, "cloudflare_browser_status", lambda: {"configured": True})
    monkeypatch.setattr(adapter, "browserless_status", lambda: {"configured": True})
    calls = []

    def cloudflare(url):
        calls.append("cloudflare")
        raise adapter.BrowserUseNotConfigured("temporary Browser Run failure")

    def browserless(url, output_format, include_links):
        calls.append("browserless")
        return {"status": "completed", "provider": "browserless", "content": "Rendered content"}

    monkeypatch.setattr(adapter, "run_cloudflare_playwright_fetch", cloudflare)
    monkeypatch.setattr(adapter, "run_browserless_fetch", browserless)

    result = adapter.run_browser_fetch("https://example.com")
    assert calls == ["cloudflare", "browserless"]
    assert result["provider"] == "browserless"
    assert result["fallback_from"] == "cloudflare_unavailable_or_failed"


def test_auto_router_returns_incomplete_http_result_when_renderers_are_unavailable(monkeypatch):
    monkeypatch.setenv("FLYBRAIN_WEB_FETCH_PROVIDER", "auto")
    monkeypatch.setattr(adapter, "_validate_url", lambda value: value)
    monkeypatch.setattr(adapter, "_run_http_browser_fetch", lambda *args: {
        "status": "completed", "provider": "http", "content": "Loading"
    })
    monkeypatch.setattr(adapter, "cloudflare_browser_status", lambda: {"configured": False})
    monkeypatch.setattr(adapter, "browserless_status", lambda: {"configured": False})

    result = adapter.run_browser_fetch("https://example.com")
    assert result["provider"] == "http"
    assert "may be incomplete" in result["note"]
