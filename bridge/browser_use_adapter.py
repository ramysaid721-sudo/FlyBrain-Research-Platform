"""Browser Use adapter for FlyBrain MCP. Local-first, optional dependency."""
from __future__ import annotations
import os
import re
from urllib.parse import urlparse
from ipaddress import ip_address
from urllib.request import urlopen

class BrowserUseNotConfigured(RuntimeError):
    pass

def _validate_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("url must be a valid URL under 2048 characters")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only absolute HTTPS URLs are accepted")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Local and internal hostnames are blocked")
    try:
        addr = ip_address(host)
    except ValueError:
        addr = None
    if addr is not None and (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved):
        raise ValueError("Private, loopback, link-local, and reserved IP addresses are blocked")
    return url.strip()

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
        if os.environ.get("BROWSER_USE_ALLOW_CLOUD", "").lower() != "true":
            raise BrowserUseNotConfigured("Browser Use Cloud is disabled until possible usage charges are explicitly approved")
        if not os.environ.get("BROWSER_USE_API_KEY"):
            raise BrowserUseNotConfigured("BROWSER_USE_API_KEY is not configured")
        from browser_use import ChatBrowserUse
        return ChatBrowserUse()
    raise BrowserUseNotConfigured("Unsupported BROWSER_USE_PROVIDER")

def browser_use_status() -> dict:
    provider = os.environ.get("BROWSER_USE_PROVIDER", "ollama").strip().lower()
    try:
        import browser_use
        installed, version = True, getattr(browser_use, "__version__", "unknown")
    except ImportError:
        installed, version = False, None
    ready, reason = installed, None
    if provider == "ollama":
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
    return {"installed": installed, "version": version, "provider": provider, "ready": bool(ready),
            "browser_mode": "local Chromium" if provider != "browser-use-cloud" else "Browser Use Cloud",
            "reason": reason, "persistent_profiles": False,
            "note": "Browser automation is not active until a live task succeeds."}

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
        return {"status": "approval_required", "message": "This goal may modify an account or submit information. Explicit approval is required; set allow_side_effects=true only after approval.", "url": target, "steps": 0}
    status = browser_use_status()
    if not status["installed"]:
        raise BrowserUseNotConfigured("Install the optional dependency from requirements-browser-use.txt")
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

def run_browser_search(query: str, max_results: int = 8) -> dict:
    """Search the public web through a rendered search results page."""
    from urllib.parse import quote_plus
    if not isinstance(query, str) or not query.strip() or len(query) > 1500:
        raise ValueError("query must be a non-empty string of at most 1500 characters")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20")
    target = "https://html.duckduckgo.com/html/?q=" + quote_plus(query.strip())
    goal = (
        f"Search the web for: {query.strip()}. Inspect the search results page and return up to {max_results} "
        "relevant results as JSON objects with title, url, snippet, and source_domain. "
        "Do not open ads. Prefer primary or authoritative sources and preserve the exact URLs."
    )
    result = run_browser_task(target, goal, max_steps=12)
    result["query"] = query.strip()
    return result


def run_browser_fetch(url: str, output_format: str = "markdown", include_links: bool = True) -> dict:
    """Fetch and extract rendered page content from a public HTTPS page."""
    if output_format not in {"markdown", "text", "json"}:
        raise ValueError("output_format must be markdown, text, or json")
    if not isinstance(include_links, bool):
        raise ValueError("include_links must be boolean")
    goal = (
        f"Read the page at the target URL and extract its main content in {output_format} format. "
        "Preserve headings, dates, tables, and factual details. "
        + ("Include relevant source links with their exact URLs." if include_links else "Do not include a link list.")
        + " Do not infer missing facts; report if the page is blocked or unavailable."
    )
    return run_browser_task(url, goal, max_steps=10)


def run_browser_research(question: str, max_sources: int = 6) -> dict:
    """Perform a multi-source browser research task with explicit source URLs."""
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("question must be a non-empty string of at most 4000 characters")
    if isinstance(max_sources, bool) or not isinstance(max_sources, int) or not 2 <= max_sources <= 12:
        raise ValueError("max_sources must be between 2 and 12")
    from urllib.parse import quote_plus
    target = "https://html.duckduckgo.com/html/?q=" + quote_plus(question.strip())
    goal = (
        f"Research this question: {question.strip()}. Search for at least {max_sources} independent, relevant "
        "sources where available. Open the strongest sources, prioritize primary research and official documents, "
        "cross-check key claims, and return a concise report with claim, evidence, publication date when available, "
        "source title, and exact source URL. Separate established facts from uncertainty. Never invent citations."
    )
    result = run_browser_task(target, goal, max_steps=24)
    result["question"] = question.strip()
    return result
