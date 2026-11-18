"""Browser Use adapter for FlyBrain MCP. Local-first, optional dependency."""
from __future__ import annotations
import os
import re
from urllib.parse import urlparse
from ipaddress import ip_address

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
        reason = "Local Ollama endpoint selected; verify Ollama and the configured model are running on the same host."
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
