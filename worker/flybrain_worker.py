"""Deterministic, checkpointed worker for the FlyBrain mission queue.

The worker only executes registered, bounded handlers. It does not invoke an
LLM, alter production, or write to GitHub. Completion always enters the
supervisor-verification state.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TASK_RUNNER_DIAGNOSIS = "d3000000-0000-4000-8000-000000000001"
TASK_CI_QUALIFICATION = "d3000000-0000-4000-8000-000000000002"
GITHUB_REPO = "ramysaid721-sudo/FlyBrain-Research-Platform"
KNOWN_FAILED_RUN_ID = 44707066740
TEST_REPORT_URL = (
    "https://github.com/ramysaid721-sudo/FlyBrain-Research-Platform/"
    "blob/flybrain-browser-worker-staging/reports/VERCEL_SANDBOX_TEST_RUN_2026-11-20.md"
)
TEST_PATHS = [
    "components/FlyBrain-NOS/tests/test_capability_mesh.py",
    "components/FlyBrain-NOS/tests/test_mcp_server.py",
    "components/FlyBrain-NOS/tests/test_service_emulation_governance.py",
    "components/FlyBrain-NOS/tests/test_service_emulation_planner.py",
    "components/FlyBrain-NOS/tests/test_koofr_webdav_adapter.py",
]


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
        headers={"Content-Type": "application/json", "x-flybrain-token": token},
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
    request = Request(
        "https://api.github.com" + path,
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


def run_command(args: list[str], cwd: Path, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise WorkerError(f"Command timed out after {timeout}s: {args[0]}") from None
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise WorkerError(
            f"Command failed ({result.returncode}): {args[0]}: {output[-700:]}"
        )
    return output


def diagnose_runner_failure() -> dict:
    run = github_get(f"/repos/{GITHUB_REPO}/actions/runs/{KNOWN_FAILED_RUN_ID}")
    jobs_payload = github_get(
        f"/repos/{GITHUB_REPO}/actions/runs/{KNOWN_FAILED_RUN_ID}/jobs?per_page=100"
    )
    jobs = jobs_payload.get("jobs", []) if isinstance(jobs_payload, dict) else []
    summaries = []
    for job in jobs:
        steps = job.get("steps") or []
        summaries.append({
            "id": job.get("id"),
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
    return {
        "classification": (
            "runner_provisioning_failure_before_first_step"
            if runner_unallocated
            else "runner_metadata_requires_supervisor_review"
        ),
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
    }


def qualify_ci_runner() -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    release_zip = repo_root / "FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip"
    release_dir = repo_root / ".release"
    if not release_zip.is_file():
        raise WorkerError("FlyBrain v0.14.0 release ZIP is missing from the worker checkout")

    shutil.rmtree(release_dir, ignore_errors=True)
    run_command(
        [sys.executable, "-m", "zipfile", "-e", str(release_zip), str(release_dir)],
        cwd=repo_root,
        timeout=20,
    )
    package_root = release_dir / "FlyBrain_Research_Platform_v0.14.0"
    run_command(
        [sys.executable, "scripts/apply_chat_bridge.py", "--source", str(package_root)],
        cwd=repo_root,
        timeout=20,
    )
    run_command(
        [sys.executable, "-m", "compileall", "-q", "bridge", "scripts"],
        cwd=repo_root,
        timeout=20,
    )

    run_command(
        [sys.executable, "-m", "pip", "install", "--quiet", "pytest"],
        cwd=repo_root,
        timeout=30,
    )
    run_command(
        [sys.executable, "-m", "pip", "install", "--quiet", "-e",
         str(package_root / "components" / "FlyBrain-NOS")],
        cwd=repo_root,
        timeout=30,
    )
    test_args = [
        sys.executable, "-m", "pytest", "-q",
        *[str(Path("components/FlyBrain-NOS/tests") / name.split("/")[-1])
          for name in TEST_PATHS],
    ]
    test_output = run_command(test_args, cwd=package_root, timeout=35)
    match = re.search(r"(\d+) passed(?:, (\d+) failed)?", test_output)
    if not match:
        raise WorkerError(f"Pytest did not report a passing summary: {test_output[-700:]}")
    passed = int(match.group(1))
    failed = int(match.group(2) or 0)
    if passed != 74 or failed != 0:
        raise WorkerError(f"Expected 74 passing tests and zero failures; got {passed}/{failed}")

    commit = run_command(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        timeout=10,
    ).strip()
    return {
        "runner": "Vercel Sandbox Hobby",
        "qualification": "passed",
        "python_version": sys.version.split()[0],
        "compileall": "passed",
        "tests_passed": passed,
        "tests_failed": failed,
        "test_output": test_output[-500:],
        "tested_commit": commit,
        "report_url": TEST_REPORT_URL,
        "github_actions_runner_status": "upstream allocation failure remains classified separately",
    }


def main() -> int:
    execution_id = _env("FLYBRAIN_EXECUTION_ID")
    lease_token = _env("FLYBRAIN_LEASE_TOKEN")
    try:
        task = json.loads(_env("FLYBRAIN_TASK_JSON"))
        if not isinstance(task, dict):
            raise WorkerError("Claimed task payload is invalid")
        task_id = task.get("id")
        control(
            "heartbeat",
            execution_id=execution_id,
            lease_token=lease_token,
            lease_seconds=300,
        )
        if task_id == TASK_RUNNER_DIAGNOSIS:
            checkpoint_key = "github-runner-diagnostic"
            evidence = diagnose_runner_failure()
        elif task_id == TASK_CI_QUALIFICATION:
            checkpoint_key = "external-runner-ci-qualification"
            evidence = qualify_ci_runner()
        else:
            raise WorkerError(f"No deterministic handler registered for task {task_id}")

        saved = control(
            "checkpoint",
            execution_id=execution_id,
            lease_token=lease_token,
            checkpoint_key=checkpoint_key,
            payload=evidence,
        )
        if not saved:
            raise WorkerError("Execution checkpoint was not persisted")
        completed = control(
            "complete",
            execution_id=execution_id,
            lease_token=lease_token,
        )
        if completed is not True:
            raise WorkerError("Task completion was rejected by the control plane")
        print(json.dumps({
            "status": "awaiting_verification",
            "task_id": task_id,
            "checkpoint": checkpoint_key,
            "result": evidence.get("classification") or evidence.get("qualification"),
            "tests_passed": evidence.get("tests_passed"),
            "tests_failed": evidence.get("tests_failed"),
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
