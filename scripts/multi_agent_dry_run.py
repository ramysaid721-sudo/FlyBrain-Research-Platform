#!/usr/bin/env python3
"""Offline, deterministic proof of FlyBrain's multi-agent task handoff.

This harness uses the packaged URCAL SQLiteQueue and mock role handlers only.
It never imports ModelHub provider discovery, reads credentials, or opens a
network connection. Use synthetic/public test input only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


class DryRunError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_sqlite_queue_class(release_root: str | Path):
    """Load the exact URCAL queue module from an extracted v0.14.0 release."""
    source = Path(release_root) / "components" / "URCAL" / "urcal" / "queue.py"
    if not source.is_file():
        raise FileNotFoundError(f"URCAL queue module not found under release root: {source}")
    spec = importlib.util.spec_from_file_location("flybrain_dryrun_urcal_queue", source)
    if spec is None or spec.loader is None:
        raise ImportError("could not load the packaged URCAL queue module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SQLiteQueue


class DryRunLedger:
    """Local audit ledger; stores hashes and state transitions, not prompt text."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        with sqlite3.connect(self.path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    parent_task_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    state TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL,
                    output_sha256 TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    event_at REAL NOT NULL,
                    detail_code TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES agent_tasks(task_id)
                );
                """
            )

    def create_task(self, task_id: str, parent_task_id: str, role: str, payload: dict) -> None:
        now = time.time()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO agent_tasks(task_id,parent_task_id,role,state,input_sha256,created_at,updated_at) "
                "VALUES(?,?,?,'queued',?,?,?)",
                (task_id, parent_task_id, role, digest(payload), now, now),
            )
            db.execute(
                "INSERT INTO agent_events(task_id,state,event_at,detail_code) VALUES(?,?,?,?)",
                (task_id, "queued", now, "task_enqueued"),
            )

    def transition(self, task_id: str, state: str, *, output: dict | None = None,
                   detail_code: str) -> None:
        now = time.time()
        output_hash = digest(output) if output is not None else None
        with sqlite3.connect(self.path) as db:
            cur = db.execute(
                "UPDATE agent_tasks SET state=?,output_sha256=COALESCE(?,output_sha256),updated_at=? "
                "WHERE task_id=?",
                (state, output_hash, now, task_id),
            )
            if cur.rowcount != 1:
                raise DryRunError("unknown task in audit ledger")
            db.execute(
                "INSERT INTO agent_events(task_id,state,event_at,detail_code) VALUES(?,?,?,?)",
                (task_id, state, now, detail_code),
            )

    def task_rows(self) -> list[tuple]:
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT task_id,role,state,input_sha256,output_sha256 "
                "FROM agent_tasks ORDER BY created_at,task_id"
            ).fetchall()

    def event_rows(self) -> list[tuple]:
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT task_id,state,detail_code FROM agent_events ORDER BY event_id"
            ).fetchall()


class MockOnlyOrchestrator:
    """Sequential dependency-aware task handoff with deterministic mock agents."""

    ROLES = ("proposer", "independent_critic", "synthesizer")

    def __init__(self, queue, ledger: DryRunLedger):
        self.queue = queue
        self.ledger = ledger

    @staticmethod
    def _mock_agent(role: str, payload: dict) -> dict:
        if role == "proposer":
            task = payload["task"]
            return {
                "role": role,
                "proposal": "Synthetic proposal for task " + digest(task)[:12],
                "assumptions": ["input is synthetic/public test material"],
                "evidence_required": ["independent source or deterministic test"],
            }
        if role == "independent_critic":
            proposal = payload["proposal"]
            return {
                "role": role,
                "critique": "Synthetic independent critique; no factual claim is asserted.",
                "counterpoints": ["verify assumptions", "test failure cases"],
                "proposal_sha256": digest(proposal),
            }
        if role == "synthesizer":
            proposal, critique = payload["proposal"], payload["critique"]
            return {
                "role": role,
                "summary": "Offline task handoff completed; this is not a research conclusion.",
                "proposal_sha256": digest(proposal),
                "critique_sha256": digest(critique),
                "disagreements_preserved": True,
            }
        raise DryRunError("role is not allowlisted")

    def _execute_stage(self, run_id: str, role: str, payload: dict) -> dict:
        task_id = f"{run_id}:{role}"
        worker_id = f"dry-run-{role}"
        job = {
            "task_id": task_id,
            "parent_task_id": run_id,
            "role": role,
            "payload": payload,
        }
        self.ledger.create_task(task_id, run_id, role, payload)
        queued = self.queue.enqueue(job)
        if queued.get("duplicate"):
            raise DryRunError("duplicate task ID rejected by queue")
        claimed = self.queue.dequeue(timeout=0, worker_id=worker_id, lease_seconds=30)
        if claimed is None or claimed.get("task_id") != task_id:
            raise DryRunError("queued task could not be claimed")
        self.ledger.transition(task_id, "running", detail_code="worker_claimed")
        try:
            output = self._mock_agent(role, claimed["payload"])
            self.ledger.transition(
                task_id, "completed", output=output, detail_code="mock_agent_completed"
            )
            self.queue.ack(task_id, worker_id=worker_id)
            queue_state = self.queue.status(task_id)["state"]
            if queue_state != "done":
                raise DryRunError("queue acknowledgement was not persisted")
            return {
                "task_id": task_id,
                "role": role,
                "state": "completed",
                "output_sha256": digest(output),
                "output": output,
            }
        except Exception as exc:
            try:
                self.ledger.transition(
                    task_id, "failed", detail_code=type(exc).__name__
                )
            finally:
                try:
                    self.queue.nack(
                        task_id, error=exc, worker_id=worker_id, delay_seconds=0
                    )
                except Exception:
                    pass
            raise

    def run(self, task: str) -> dict:
        if not isinstance(task, str) or not task.strip():
            raise DryRunError("task must be a non-empty string")
        if len(task) > 4000:
            raise DryRunError("task exceeds the 4000-character dry-run limit")
        run_id = "dryrun-" + str(uuid.uuid4())
        proposer = self._execute_stage(run_id, "proposer", {"task": task})
        critic = self._execute_stage(
            run_id, "independent_critic",
            {"task": task, "proposal": proposer["output"]},
        )
        synthesis = self._execute_stage(
            run_id, "synthesizer",
            {"task": task, "proposal": proposer["output"], "critique": critic["output"]},
        )
        return {
            "run_id": run_id,
            "mode": "offline_mock_only",
            "network_calls": 0,
            "provider_credentials_used": 0,
            "stages": [
                {k: v for k, v in stage.items() if k != "output"}
                for stage in (proposer, critic, synthesis)
            ],
            "synthesis": synthesis["output"],
            "audit_task_count": len(self.ledger.task_rows()),
            "audit_event_count": len(self.ledger.event_rows()),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", required=True,
                        help="extracted FlyBrain v0.14.0 release root")
    parser.add_argument("--task", default="Synthetic architecture review for offline orchestration validation.",
                        help="synthetic/public test task only; stored temporarily in the local queue")
    args = parser.parse_args()
    queue_cls = load_sqlite_queue_class(args.release_root)
    with tempfile.TemporaryDirectory(prefix="flybrain-agent-dryrun-") as tmp:
        root = Path(tmp)
        queue = queue_cls(root / "queue.sqlite3", max_attempts=1)
        ledger = DryRunLedger(root / "ledger.sqlite3")
        result = MockOnlyOrchestrator(queue, ledger).run(args.task)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
