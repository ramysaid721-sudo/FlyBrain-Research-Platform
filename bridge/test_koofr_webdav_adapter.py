import base64
import urllib.error

import pytest

from flybrain_os import koofr_webdav_adapter as adapter


class FakeResponse:
    def __init__(self, body=b"", status=200):
        self.body = body
        self.status = status

    def read(self, size=-1):
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def configure(monkeypatch, write=False):
    monkeypatch.setenv("KOOFR_WEBDAV_USERNAME", "user@example.net")
    monkeypatch.setenv("KOOFR_WEBDAV_APP_PASSWORD", "secret-app-password")
    monkeypatch.setenv("FLYBRAIN_KOOFR_WEBDAV_ALLOW_WRITE", "true" if write else "false")


def test_status_never_exposes_credentials(monkeypatch):
    configure(monkeypatch)
    result = adapter.koofr_webdav_status()
    assert result["configured"] is True
    assert result["connection_verified"] is False
    assert result["ready"] is False
    assert result["write_enabled"] is False
    assert "secret-app-password" not in str(result)


def test_status_reports_unconfigured_without_credentials(monkeypatch):
    monkeypatch.delenv("KOOFR_WEBDAV_USERNAME", raising=False)
    monkeypatch.delenv("KOOFR_WEBDAV_APP_PASSWORD", raising=False)
    assert adapter.koofr_webdav_status()["ready"] is False


@pytest.mark.parametrize("key", ["../escape", "/absolute", "a//b", "a/./b", "a/../b", "a\\b"])
def test_unsafe_object_keys_are_rejected(key):
    with pytest.raises(ValueError):
        adapter._object_url(key)


def test_read_uses_fixed_https_host_and_returns_base64(monkeypatch):
    configure(monkeypatch)
    captured = {}
    def fake_open(request):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse(b"hello")
    monkeypatch.setattr(adapter, "_open", fake_open)
    result = adapter.koofr_webdav_read("FlyBrain/test.txt")
    assert captured["url"] == "https://app.koofr.net/dav/Koofr/FlyBrain/test.txt"
    assert captured["method"] == "GET"
    assert captured["authorization"].startswith("Basic ")
    assert result["content_base64"] == base64.b64encode(b"hello").decode()


def test_read_rejects_oversized_objects(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(adapter, "_open", lambda request: FakeResponse(b"x" * (adapter.MAX_OBJECT_BYTES + 1)))
    with pytest.raises(adapter.KoofrStorageError):
        adapter.koofr_webdav_read("large.bin")


def test_write_requires_both_per_call_and_server_opt_in(monkeypatch):
    configure(monkeypatch, write=False)
    with pytest.raises(adapter.KoofrStorageError):
        adapter.koofr_webdav_write("a.txt", base64.b64encode(b"x").decode(), True)
    configure(monkeypatch, write=True)
    with pytest.raises(adapter.KoofrStorageError):
        adapter.koofr_webdav_write("a.txt", base64.b64encode(b"x").decode(), False)


def test_write_sends_only_to_fixed_koofr_endpoint_and_reports_metadata(monkeypatch):
    configure(monkeypatch, write=True)
    captured = {}
    def fake_open(request):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = request.data
        return FakeResponse(status=201)
    monkeypatch.setattr(adapter, "_open", fake_open)
    result = adapter.koofr_webdav_write("FlyBrain/test.txt", base64.b64encode(b"hello").decode(), True)
    assert captured["url"] == "https://app.koofr.net/dav/Koofr/FlyBrain/test.txt"
    assert captured["method"] == "PUT"
    assert captured["body"] == b"hello"
    assert result["size_bytes"] == 5


def test_write_rejects_invalid_base64(monkeypatch):
    configure(monkeypatch, write=True)
    with pytest.raises(ValueError):
        adapter.koofr_webdav_write("a.txt", "not base64!", True)


def test_write_rejects_redirects(monkeypatch):
    configure(monkeypatch, write=True)
    def fake_open(request):
        raise urllib.error.HTTPError(request.full_url, 302, "redirect", {}, None)
    monkeypatch.setattr(adapter, "_open", fake_open)
    with pytest.raises(adapter.KoofrStorageError, match="redirect rejected"):
        adapter.koofr_webdav_write("a.txt", base64.b64encode(b"x").decode(), True)


def test_read_only_probe_verifies_connection_without_writing(monkeypatch):
    configure(monkeypatch)
    captured = {}
    def fake_open(request):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["depth"] = request.get_header("Depth")
        return FakeResponse(b"<multistatus/>", status=207)
    monkeypatch.setattr(adapter, "_open", fake_open)
    result = adapter.koofr_webdav_probe()
    assert captured["method"] == "PROPFIND"
    assert captured["url"] == adapter.KOOFR_WEBDAV_ENDPOINT
    assert captured["depth"] == "0"
    assert result["connection_verified"] is True


def test_probe_rejects_authentication_failure(monkeypatch):
    configure(monkeypatch)
    def fake_open(request):
        raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, None)
    monkeypatch.setattr(adapter, "_open", fake_open)
    with pytest.raises(adapter.KoofrStorageError, match="application-specific"):
        adapter.koofr_webdav_probe()
