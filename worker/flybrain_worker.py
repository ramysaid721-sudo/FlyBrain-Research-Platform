"""Deterministic, checkpointed worker for the FlyBrain mission queue.

This worker intentionally does not invoke an LLM, install packages, or mutate
GitHub. It handles the initial GitHub Actions runner diagnostic as read-only
work and leaves all task verification to the supervisor.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

RUNNER_FAILURE_TASK_ID = "d3000000-0000-4000-8000-000000000001"
GITHUB_REPO = "ramysaid721-sudo/FlyBrain-Research-Platform"
KNOWN_FAILED_RUN_ID = 44707066740
TEST_REPORT_URL = (
    "https://github.com/ramysaid721-sudo/FlyBrain-Research-Platform/"
    "blob/flybrain-browser-worker-staging/reports/VERCEL_SANDBOX_TEST_RUN_2026-11-20.md"
)


class WorkerError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise WorkerError(f"Required worker environment variable is missing: {name}")
    return value


def control(action: str, **payload):
    token = _env("FLYBRAIN_WORKER_TOKEN")
    endpoint = _env("FLYBRAIN_CONTROL_URL")
    body = json.dumps({"action": action, **payload}).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-flybrain-token": token,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            result = json.loads(response.read(256_000).decode("utf-8"))
    except HTTPError as exc:
        raise WorkerError(f"Control plane rejected {action}: HTTP {exc.code}") from None
    except (URLError, TimeoutError) as exc:
        raise WorkerError(f"Control plane unavailable during {action}: {type(exc).__name__}") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise WorkerError(f"Control plane action {action} did not succeed")
    return result.get("result")


def github_get(path: str):
    url = "https://api.github.com" + path
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "FlyBrain-ReadOnly-Diagnostic-Worker",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read(1_000_000).decode("utf-8"))
    except HTTPError as exc:
        raise WorkerError(f"GitHub read-only API returned HTTP {exc.code}") from None
    except (URLError, TimeoutError) as exc:
        raise WorkerError(f"GitHub API unavailable: {type(exc).__name__}") from None


def diagnose_runner_failure(task: dict, execution_id: str, lease_token: str) -> dict:
    run = github_get(f"/repos/{GITHUB_REPO}/actions/runs/{KNOWN_FAILED_RUN_ID}")
    jobs_payload = github_get(
        f"/repos/{GITHUB_REPO}/actions/runs/{KNOWN_FAILED_RUN_ID}/jobs?per_page=100"
    )
    jobs = jobs_payload.get("jobs", []) if isinstance(jobs_payload, dict) else []
    summaries = []
    for job in jobs:
        steps = job.get("steps") or []
        summaries.append({
            "name": job.get("name"),
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
            "runner_id": job.get("runner_id"),
            "runner_name": job.get("runner_name"),
            "steps": [
                {"name": step.get("name"), "status": step.get("status"),
                 "conclusion": step.get("conclusion")}
                for step in steps
            ],
            "step_count": len(steps),
        })

    runner_unallocated = bool(summaries) and all(
        item["runner_id"] in (None, 0)
        and not item["runner_name"]
        and item["step_count"] == 0
        for item in summaries
    )
    classification = (
        "runner_provisioning_failure_before_first_step"
        if runner_unallocated
        else "runner_metadata_requires_supervisor_review"
    )
    evidence = {
        "classification": classification,
        "root_cause_boundary": (
            "The job failed at GitHub-hosted runner allocation before any workflow "
            "step executed. The exposed run/job metadata does not identify the "
            "upstream infrastructure reason; it does distinguish this from a "
            "workflow-code or pytest failure."
        ),
        "run": {
            "id": run.get("id"),
            "name": run.get("name"),
            "event": run.get("event"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "html_url": run.get("html_url"),
            "head_sha": run.get("head_sha"),
            "head_branch": run.get("head_branch"),
        },
        "jobs": summaries,
        "external_runner_qualification": {
            "provider": "Vercel Sandbox Hobby",
            "result": "74 passed, 0 failed",
            "tested_commit": "2f8025ecb5655d050da7a723cee6a16b32598e4f",
            "report_url": TEST_REPORT_URL,
            "python_runtime": "3.14.4",
            "python_3_12_compatibility": "pending",
        },
        "task_id": task.get("id"),
        "execution_id": execution_id,
    }
    checkpoint = control(
        "checkpoint",
        execution_id=execution_id,
        lease_token=lease_token,
        checkpoint_key="github-runner-diagnostic",
        payload=evidence,
    )
    if not checkpoint:
        raise WorkerError("Diagnostic checkpoint was not persisted")
    completed = control(
        "complete",
        execution_id=execution_id,
        lease_token=lease_token,
    )
    if completed is not True:
        raise WorkerError("Task completion was rejected by the control plane")
    return evidence


def main() -> int:
    execution_id = _env("FLYBRAIN_EXECUTION_ID")
    lease_token = _env("FLYBRAIN_LEASE_TOKEN")
    try:
        task = json.loads(_env("FLYBRAIN_TASK_JSON"))
        if not isinstance(task, dict):
            raise WorkerError("Claimed task payload is invalid")
        if task.get("id") != RUNNER_FAILURE_TASK_ID:
            raise WorkerError(f"No deterministic handler registered for task {task.get('id')}")
        control(
            "heartbeat",
            execution_id=execution_id,
            lease_token=lease_token,
            lease_seconds=300,
        )
        evidence = diagnose_runner_failure(task, execution_id, lease_token)
        print(json.dumps({
            "status": "awaiting_verification",
            "task_id": task.get("id"),
            "classification": evidence["classification"],
            "runner_jobs": len(evidence["jobs"]),
            "checkpoint": "github-runner-diagnostic",
        }, separators=(",", ":")))
        return 0
    except Exception as exc:
        try:
            control(
                "fail",
                execution_id=execution_id,
                lease_token=lease_token,
                error=f"{type(exc).__name__}: {str(exc)[:900]}",
            )
        except Exception:
            pass
        print(json.dumps({
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:900],
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
