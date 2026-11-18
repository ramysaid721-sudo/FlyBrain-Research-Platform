"""Policy-first tool lifecycle manager for FlyBrain.

This module deliberately does not install packages inside the public MCP/serverless
process. It provides inventory, candidate assessment, and a fail-closed policy
decision. Installation and upgrades belong in a separately isolated worker.
"""
from __future__ import annotations

import importlib.metadata
import json
import os
import re
from pathlib import Path
from typing import Any

POLICY_VERSION = "1.0.0"
DEFAULT_ALLOWLIST = {
    "pip-audit": {"purpose": "dependency vulnerability auditing", "risk": "low"},
    "bandit": {"purpose": "Python static security analysis", "risk": "low"},
    "ruff": {"purpose": "Python linting and static checks", "risk": "low"},
    "pytest": {"purpose": "automated tests", "risk": "low"},
}
DENIED_NAMES = {
    "curl", "wget", "nc", "netcat", "nmap", "masscan", "metasploit",
    "sqlmap", "hydra", "john", "hashcat", "proxychains", "tor",
}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class ToolPolicyError(ValueError):
    """Raised when a requested tool operation violates policy."""


def _normalise_name(name: str) -> str:
    if not isinstance(name, str) or not NAME_RE.fullmatch(name.strip()):
        raise ToolPolicyError("Invalid package/tool name")
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


class ToolLifecycleManager:
    """Read-only inventory and fail-closed candidate policy for the MCP runtime."""

    def __init__(self) -> None:
        raw = os.environ.get("FLYBRAIN_TOOL_ALLOWLIST", "")
        self.allowlist = dict(DEFAULT_ALLOWLIST)
        # Environment configuration can only narrow the built-in safe set.
        if raw.strip():
            requested = {_normalise_name(x) for x in raw.split(",") if x.strip()}
            self.allowlist = {k: v for k, v in self.allowlist.items() if k in requested}

    def status(self) -> dict[str, Any]:
        installed = {}
        for dist in importlib.metadata.distributions():
            name = dist.metadata.get("Name")
            if name:
                installed[_normalise_name(name)] = dist.version
        return {
            "status": "ready",
            "component": "FlyBrain Tool Lifecycle Manager",
            "policy_version": POLICY_VERSION,
            "mode": "policy-and-inventory-only",
            "installed_python_packages": len(installed),
            "automatic_installation": False,
            "automatic_updates": False,
            "isolated_worker_ready": False,
            "reason": (
                "The current Vercel serverless runtime has no isolated package "
                "installation worker, durable job queue, or rollback environment."
            ),
            "security": {
                "fail_closed": True,
                "no_shell_execution": True,
                "no_runtime_package_install": True,
                "no_secrets_exposed": True,
                "least_privilege": True,
            },
        }

    def catalog(self) -> dict[str, Any]:
        return {
            "status": "completed",
            "policy_version": POLICY_VERSION,
            "approved_low_risk_candidates": [
                {"name": name, **meta, "installation": "requires isolated worker"}
                for name, meta in sorted(self.allowlist.items())
            ],
            "blocked_high_impact_examples": sorted(DENIED_NAMES),
            "note": "Catalog entries are policy candidates, not installed tools.",
        }

    def assess(self, name: str, version: str = "", source: str = "") -> dict[str, Any]:
        normal = _normalise_name(name)
        if version and (not isinstance(version, str) or len(version) > 80 or not re.fullmatch(r"[A-Za-z0-9.*+!_-]+", version)):
            raise ToolPolicyError("Invalid version constraint")
        if source and (not isinstance(source, str) or len(source) > 300):
            raise ToolPolicyError("Invalid source descriptor")
        if normal in DENIED_NAMES:
            return {
                "status": "blocked", "name": normal,
                "reason": "This high-impact tool is not eligible for automatic installation.",
                "requires_human_security_review": True,
            }
        if normal not in self.allowlist:
            return {
                "status": "review_required", "name": normal,
                "reason": "Tool is not in the narrowly scoped low-risk allowlist.",
                "requires_human_security_review": True,
                "installation_authorized": False,
            }
        return {
            "status": "eligible_for_isolated_testing",
            "name": normal,
            "version_constraint": version or "latest-not-pinned",
            "source": source or "package index must be verified by worker",
            "purpose": self.allowlist[normal]["purpose"],
            "installation_authorized": False,
            "next_step": "An isolated worker must verify provenance, hashes, licenses, dependencies, run tests, and produce a signed artifact before activation.",
        }


_MANAGER: ToolLifecycleManager | None = None


def manager() -> ToolLifecycleManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ToolLifecycleManager()
    return _MANAGER


def tool_manager_status() -> dict[str, Any]:
    return manager().status()


def tool_catalog() -> dict[str, Any]:
    return manager().catalog()


def assess_tool(name: str, version: str = "", source: str = "") -> dict[str, Any]:
    return manager().assess(name, version, source)
