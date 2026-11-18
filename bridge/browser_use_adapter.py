"""Browser automation and safe HTTP research adapters for FlyBrain.

The HTTP research path is serverless-friendly and does not require a hosted browser
or external LLM. Interactive browser control remains an optional Browser Use extra.
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
from html.parser import HTMLParser
from ipaddress import ip_address, ip_address as _ip
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

class BrowserUseNotConfigured(RuntimeError):
    pass


def _resolve_public_host(host: str) -> None:
    try:
        literal = ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            addresses = [_ip(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
        except OSError as exc:
            raise ValueError("The target hostname could not be resolved") from exc
    if not addresses or any(not addr.is_global for addr in addresses):
        raise ValueError("Private, loopback, link-local, reserved, and non-public network targets are blocked")


def _validate_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("url must be a valid URL under 2048 characters")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only absolute HTTPS URLs are accepted")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Local and internal hostnames are blocked")
    _resolve_public_host(host)
    return url.strip()


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_get(url: str, timeout: float = 10.0, max_bytes: int = 1_500_000):
    target = _validate_url(url)
    request = Request(target, headers={
        "User-Agent": "Mozilla/5.0 (compatible; FlyBrainResearch/1.0; +https://github.com/ramysaid721-sudo/FlyBrain-Research-Platform)",
        "Accept": "text/html,application/xhtml+xml,text/plain,application/json;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.8",
    })
    opener = build_opener(_SafeRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = _validate_url(response.geturl())
            content_type = response.headers.get("Content-Type", "")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("The page exceeded the extraction size limit")
            charset_match = re.search(r"charset=([w.-]+)", content_type, re.I)
            charset = charset_match.group(1) if charset_match else "utf-8"
            try:
                body = data.decode(charset, errors="replace")
            except LookupError:
                body = data.decode("utf-8", errors="replace")
            return final_url, content_type, body
    except HTTPError as exc:
        raise ValueError(f"Website returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError(f"Website request failed: {type(exc.reason).__name__}") from exc


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.text_parts = []
        self.links = []
        self._in_title = False
        self._skip = 0
        self._anchor = None
        self._heading = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag in {"script", "style", "noscript", "svg", "iframe", "nav", "footer"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta" and (attrs.get("name") or "").lower() == "description":
            self.description = attrs.get("content", "")[:500]
        if tag == "link" and "canonical" in (attrs.get("rel") or "").lower():
            self.canonical = attrs.get("href", "")[:2048]
        if tag in {"h1", "h2", "h3"}:
            self._heading = int(tag[1])
            self.text_parts.append("\n" + "#" * self._heading + " ")
        if tag == "a" and attrs.get("href"):
            self._anchor = {"href": attrs.get("href", ""), "text": "", "classes": classes}

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "iframe", "nav", "footer"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"h1", "h2", "h3"}:
            self.text_parts.append("\n")
            self._heading = 0
        if tag == "a" and self._anchor:
            self.links.append(self._anchor)
            self._anchor = None
        if tag in {"p", "div", "li", "section", "article", "br"}:
            self.text_parts.append("\n")

    def handle_data(self, data):
        clean = " ".join(data.split())
        if not clean:
            return
        if self._in_title:
            self.title += clean + " "
        if self._skip:
            return
        self.text_parts.append(clean + " ")
        if self._anchor:
            self._anchor["text"] += clean + " "

    def page_text(self):
        return re.sub(r"\n{3,}", "\n\n", "".join(self.text_parts)).strip()


class _SearchParser(HTMLParser):
    def __init__(self, limit: int):
        super().__init__(convert_charrefs=True)
        self.limit = limit
        self.results = []
        self._current = None
        self._capture = None

    def _flush(self):
        if self._current is not None and self._current.get("title", "").strip():
            self.results.append(self._current)
        self._current = None
        self._capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "a" and "result__a" in classes and len(self.results) < self.limit:
            self._flush()
            self._current = {"title": "", "url": attrs.get("href", ""), "snippet": ""}
            self._capture = "title"
        elif self._current is not None and tag == "a" and ({"result__snippet", "result-snippet"} & classes):
            self._capture = "snippet"

    def handle_endtag(self, tag):
        if tag == "a":
            self._capture = None

    def handle_data(self, data):
        if self._current is None:
            return
        if self._capture == "snippet":
            self._current["snippet"] += data
        elif self._capture == "title":
            self._current["title"] += data

    def close(self):
        super().close()
        self._flush()


def _normalise_search_url(raw: str) -> str:
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    return raw


def browser_use_status() -> dict:
    provider = os.environ.get("BROWSER_USE_PROVIDER", "ollama").strip().lower()
    try:
        import browser_use
        installed, version = True, getattr(browser_use, "__version__", "unknown")
    except ImportError:
        installed, version = False, None
    ready, reason = installed, None
    if provider == "ollama":
        from urllib.request import urlopen
        endpoint = os.environ.get("BROWSER_USE_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
        if ready:
            try:
                with urlopen(endpoint + "/models", timeout=1.5) as response:
                    ready = 200 <= response.status < 300
                reason = None if ready else "The configured Ollama-compatible endpoint did not return HTTP success."
            except Exception as exc:
                ready = False
                reason = "Local model endpoint is unreachable: " + type(exc).__name__
        else:
            reason = "Browser Use is not installed."
    elif provider == "openai":
        ready = ready and bool(os.environ.get("OPENAI_API_KEY"))
        reason = None if ready else "OPENAI_API_KEY is missing."
    elif provider == "google":
        ready = ready and bool(os.environ.get("GOOGLE_API_KEY"))
        reason = None if ready else "GOOGLE_API_KEY is missing."
    elif provider == "browser-use-cloud":
        ready = ready and os.environ.get("BROWSER_USE_ALLOW_CLOUD", "").lower() == "true" and bool(os.environ.get("BROWSER_USE_API_KEY"))
        reason = None if ready else "Cloud mode is disabled or its key is missing; cloud usage may incur charges."
    else:
        ready, reason = False, "Unsupported BROWSER_USE_PROVIDER."
    return {
        "installed": installed, "version": version, "provider": provider,
        "ready": bool(ready), "interactive_browser_ready": bool(ready),
        "web_search_ready": True, "web_fetch_ready": True,
        "browser_mode": "local Chromium" if provider != "browser-use-cloud" else "Browser Use Cloud",
        "reason": reason, "persistent_profiles": False,
        "note": "HTTP search and extraction work independently. Interactive browser control is not active until a live Browser Use task succeeds.",
    }


def run_browser_task(url: str, goal: str, max_steps: int = 12, allow_side_effects: bool = False) -> dict:
    target = _validate_url(url)
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 8000:
        raise ValueError("goal must be a non-empty string of at most 8000 characters")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 30:
        raise ValueError("max_steps must be an integer between 1 and 30")
    if not isinstance(allow_side_effects, bool):
        raise ValueError("allow_side_effects must be boolean")
    mutation_terms = re.compile(r"\b(send|submit|purchase|buy|pay|delete|remove|publish|post|upload|change password|change settings|invite|book|reserve|transfer|deploy)\b", re.IGNORECASE)
    if mutation_terms.search(goal) and not allow_side_effects:
        return {"status": "approval_required", "message": "This goal may modify an account or submit information. Explicit approval is required.", "url": target, "steps": 0}
    status = browser_use_status()
    if not status["installed"]:
        raise BrowserUseNotConfigured("Interactive browser control is unavailable: install Browser Use and Chromium on a compatible persistent browser host")
    if not status["ready"]:
        raise BrowserUseNotConfigured(status.get("reason") or "Browser Use is not configured")
    try:
        from browser_use import Agent, Browser
        agent = Agent(
            task=f"Target URL: {target}\nGoal: {goal.strip()}\n\nFlyBrain policy: prefer read-only observation and extraction. Do not bypass authentication, paywalls, CAPTCHAs, access controls, or website security. Do not access local/private network resources. Never expose secrets. Report factual findings, source URLs, and incomplete steps.",
            llm=_make_llm(),
            browser=Browser("chromium") if status["browser_mode"] == "local Chromium" else Browser(),
        )
        result = agent.run_sync(max_steps=max_steps)
        final = result.final_result() if hasattr(result, "final_result") else str(result)
        steps = result.number_of_steps() if hasattr(result, "number_of_steps") else None
        error = getattr(result, "error", None)
        return {"status": "error" if error else "completed", "url": target, "goal": goal.strip(),
                "result": final, "steps": steps, "error": str(error) if error else None,
                "provider": status["provider"], "browser_mode": status["browser_mode"]}
    except BrowserUseNotConfigured:
        raise
    except Exception as exc:
        return {"status": "error", "url": target, "goal": goal.strip(),
                "error": f"{type(exc).__name__}: {str(exc)[:1200]}", "provider": status["provider"]}


def _make_llm():
    provider = os.environ.get("BROWSER_USE_PROVIDER", "ollama").strip().lower()
    model = os.environ.get("BROWSER_USE_MODEL", "qwen2.5:7b").strip()
    if provider == "ollama":
        from browser_use import ChatOpenAI
        return ChatOpenAI(model=model, base_url=os.environ.get("BROWSER_USE_BASE_URL", "http://127.0.0.1:11434/v1"), api_key=os.environ.get("BROWSER_USE_API_KEY", "ollama"))
    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise BrowserUseNotConfigured("OPENAI_API_KEY is not configured")
        from browser_use import ChatOpenAI
        return ChatOpenAI(model=model)
    if provider == "google":
        if not os.environ.get("GOOGLE_API_KEY"):
            raise BrowserUseNotConfigured("GOOGLE_API_KEY is not configured")
        from browser_use import ChatGoogle
        return ChatGoogle(model=model)
    if provider == "browser-use-cloud":
        if os.environ.get("BROWSER_USE_ALLOW_CLOUD", "").lower() != "true" or not os.environ.get("BROWSER_USE_API_KEY"):
            raise BrowserUseNotConfigured("Browser Use Cloud is disabled or not configured")
        from browser_use import ChatBrowserUse
        return ChatBrowserUse()
    raise BrowserUseNotConfigured("Unsupported BROWSER_USE_PROVIDER")


def run_browser_search(query: str, max_results: int = 8) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query) > 1500:
        raise ValueError("query must be a non-empty string of at most 1500 characters")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20")
    search_url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query.strip())
    final_url, content_type, html = _http_get(search_url, timeout=12, max_bytes=1_000_000)
    parser = _SearchParser(max_results)
    parser.feed(html)
    results = []
    for item in parser.results[:max_results]:
        url = _normalise_search_url(item.get("url", ""))
        try:
            url = _validate_url(url)
        except ValueError:
            continue
        results.append({
            "title": " ".join(item.get("title", "").split()),
            "url": url,
            "snippet": " ".join(item.get("snippet", "").split()),
            "source_domain": urlparse(url).hostname,
        })
    return {"status": "completed", "query": query.strip(), "results": results,
            "result_count": len(results), "search_engine": "DuckDuckGo HTML",
            "search_page": final_url, "content_type": content_type,
            "note": "Results are public-web search results; verify primary sources before relying on claims."}


def run_browser_fetch(url: str, output_format: str = "markdown", include_links: bool = True) -> dict:
    if output_format not in {"markdown", "text", "json"}:
        raise ValueError("output_format must be markdown, text, or json")
    if not isinstance(include_links, bool):
        raise ValueError("include_links must be boolean")
    final_url, content_type, body = _http_get(url, timeout=12, max_bytes=1_500_000)
    parser = _PageParser()
    parser.feed(body)
    content = parser.page_text()
    links = []
    if include_links:
        for item in parser.links[:100]:
            raw = item.get("href", "").strip()
            if raw.startswith("https://"):
                try:
                    safe = _validate_url(raw)
                except ValueError:
                    continue
                links.append({"text": " ".join(item.get("text", "").split())[:300], "url": safe})
    result = {
        "status": "completed", "url": final_url,
        "title": parser.title.strip()[:500],
        "description": parser.description,
        "content_type": content_type,
        "content": content[:30000],
        "links": links,
        "extraction_mode": "HTTP HTML extraction (no JavaScript execution)",
    }
    if output_format == "text":
        result["content"] = content[:30000]
    elif output_format == "markdown":
        result["content"] = content[:30000]
    elif output_format == "json":
        result["content"] = content[:30000]
    return result


def run_browser_research(question: str, max_sources: int = 6) -> dict:
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("question must be a non-empty string of at most 4000 characters")
    if isinstance(max_sources, bool) or not isinstance(max_sources, int) or not 2 <= max_sources <= 12:
        raise ValueError("max_sources must be between 2 and 12")
    search = run_browser_search(question.strip(), max_results=max_sources)
    sources = []
    for item in search["results"][:max_sources]:
        try:
            page = run_browser_fetch(item["url"], output_format="text", include_links=False)
            sources.append({
                "title": page.get("title") or item["title"],
                "url": page["url"],
                "domain": item["source_domain"],
                "search_snippet": item.get("snippet", ""),
                "page_excerpt": page.get("content", "")[:2200],
                "fetch_status": "completed",
            })
        except Exception as exc:
            sources.append({
                "title": item["title"], "url": item["url"],
                "domain": item["source_domain"], "search_snippet": item.get("snippet", ""),
                "fetch_status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            })
    return {
        "status": "completed", "question": question.strip(),
        "sources": sources, "source_count": len(sources),
        "search_engine": search.get("search_engine"),
        "method": "Search results plus direct public-page extraction; no JavaScript browser or model-generated conclusions.",
        "instruction": "Synthesize claims from these source excerpts, cite exact URLs, and distinguish retrieved evidence from inference.",
    }
