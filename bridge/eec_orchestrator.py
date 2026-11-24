"""EEC-inspired, fail-closed planning layer for FlyBrain.

Creates bounded, auditable execution plans only. It does not call models,
transfer data to providers, execute tools, or claim that agents ran.
"""
from __future__ import annotations
import hashlib
import json
import os
import uuid
from typing import Any

EEC_VERSION = "1.0.0"
MAX_OBJECTIVE_CHARS = 8_000
MAX_PARALLEL_TASKS = 4
ROLES = {
    "strategic_planner": "Decompose the objective and define acceptance criteria.",
    "research_specialist": "Collect source-backed technical or scientific evidence.",
    "systems_architect": "Design system boundaries, interfaces, and dependencies.",
    "software_engineer": "Propose implementation changes within approved scope.",
    "security_reviewer": "Review trust boundaries, secrets, permissions, and side effects.",
    "qa_verifier": "Define deterministic tests and verify acceptance criteria.",
    "code_reviewer": "Independently review implementation against acceptance criteria.",
    "performance_optimizer": "Assess latency, throughput, resource use, and cost.",
    "documentation_specialist": "Produce operator and developer documentation.",
    "synthesizer": "Reconcile findings, conflicts, evidence, and remaining gates.",
}
TASK_KINDS = {"general", "research", "engineering", "security", "performance", "documentation"}


class EECPlanError(ValueError):
    """Raised when a planning request is outside its bounded contract."""


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def eec_status() -> dict[str, Any]:
    return {
        "status": "planning_ready",
        "eec_version": EEC_VERSION,
        "planning": True,
        "bounded_parallel_plans": True,
        "live_agent_execution": False,
        "provider_inference": False,
        "external_data_transfer": False,
        "persistent_agent_ledger_provisioned": True,
        "persistent_plan_persistence_rpc": True,
        "persistent_plan_submission_endpoint": True,
        "mcp_plan_submission_configured": bool(os.environ.get("SUPABASE_EEC_LEDGER_URL") and os.environ.get("FLYBRAIN_EEC_LEDGER_TOKEN")),
        "persistent_agent_ledger_configured": bool(os.environ.get("SUPABASE_EEC_LEDGER_URL") and os.environ.get("FLYBRAIN_EEC_LEDGER_TOKEN")),
        "mcp_plan_submission_connected": False,
        "persistent_agent_ledger_connected": False,
        "zero_cost_policy": "hard_zero",
        "max_parallel_tasks": MAX_PARALLEL_TASKS,
        "roles": list(ROLES),
        "execution_blockers": [
            "Verify authenticated MCP-to-ledger submission and status readback in Staging.",
            "Connect the typed URCAL worker contract and lease-fenced task claiming.",
            "Verify fresh, model-specific zero-cost and quota evidence before live inference.",
            "Keep provider and tool permissions isolated and fail-closed.",
        ],
        "note": "Planning is available; no live agent has been invoked.",
    }


def build_plan(objective: str, task_kind: str = "general",
               data_classification: str = "internal",
               max_parallel_tasks: int = 3) -> dict[str, Any]:
    if not isinstance(objective, str) or not objective.strip() or len(objective) > MAX_OBJECTIVE_CHARS:
        raise EECPlanError(f"objective must contain 1..{MAX_OBJECTIVE_CHARS} characters")
    if not isinstance(task_kind, str) or task_kind not in TASK_KINDS:
        raise EECPlanError("unsupported task_kind")
    if not isinstance(data_classification, str) or data_classification not in {"public", "internal", "confidential", "prohibited"}:
        raise EECPlanError("unsupported data_classification")
    if type(max_parallel_tasks) is not int or not 1 <= max_parallel_tasks <= MAX_PARALLEL_TASKS:
        raise EECPlanError(f"max_parallel_tasks must be an integer from 1 to {MAX_PARALLEL_TASKS}")

    objective_hash = _digest(objective.strip())
    plan_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{EEC_VERSION}:{objective_hash}:{task_kind}:{data_classification}:{max_parallel_tasks}"))
    specs: list[tuple[str, str, list[str]]] = [("strategic_planner", "decompose", [])]
    if task_kind == "research":
        specs += [("research_specialist", "evidence_collection", ["decompose"]),
                  ("code_reviewer", "independent_evidence_review", ["evidence_collection"])]
        terminal = ["independent_evidence_review"]
    elif task_kind == "engineering":
        specs += [
            ("research_specialist", "technical_research", ["decompose"]),
            ("systems_architect", "architecture", ["decompose", "technical_research"]),
            ("software_engineer", "implementation_proposal", ["architecture"]),
            ("security_reviewer", "security_review", ["implementation_proposal"]),
            ("qa_verifier", "verification", ["implementation_proposal"]),
            ("code_reviewer", "independent_code_review", ["implementation_proposal"]),
            ("performance_optimizer", "performance_review", ["implementation_proposal"]),
        ]
        terminal = ["security_review", "verification", "independent_code_review", "performance_review"]
    elif task_kind == "security":
        specs += [("systems_architect", "trust_boundary_mapping", ["decompose"]),
                  ("security_reviewer", "security_assessment", ["trust_boundary_mapping"]),
                  ("qa_verifier", "control_validation", ["security_assessment"])]
        terminal = ["control_validation"]
    elif task_kind == "performance":
        specs += [("systems_architect", "baseline_architecture", ["decompose"]),
                  ("performance_optimizer", "bottleneck_analysis", ["baseline_architecture"]),
                  ("qa_verifier", "benchmark_design", ["bottleneck_analysis"])]
        terminal = ["benchmark_design"]
    elif task_kind == "documentation":
        specs += [("research_specialist", "fact_gathering", ["decompose"]),
                  ("documentation_specialist", "documentation_draft", ["fact_gathering"]),
                  ("code_reviewer", "factual_review", ["documentation_draft"])]
        terminal = ["factual_review"]
    else:
        specs += [("research_specialist", "evidence_collection", ["decompose"]),
                  ("systems_architect", "solution_architecture", ["decompose"]),
                  ("security_reviewer", "risk_review", ["solution_architecture"]),
                  ("qa_verifier", "acceptance_tests", ["solution_architecture"]),
                  ("performance_optimizer", "performance_review", ["solution_architecture"])]
        terminal = ["evidence_collection", "risk_review", "acceptance_tests", "performance_review"]
    specs.append(("synthesizer", "evidence_synthesis", terminal))

    ids = {key: str(uuid.uuid5(uuid.UUID(plan_id), key)) for _, key, _ in specs}
    tasks = [{
        "task_id": ids[key], "role": role, "role_description": ROLES[role],
        "task_type": key, "depends_on": [ids[d] for d in deps],
        "input_ref": {"objective_sha256": objective_hash},
        "acceptance_criteria": [
            "Return structured findings with evidence or an explicit evidence gap.",
            "Do not infer completion from another agent's status message.",
            "Do not request secrets or unapproved external data transfer.",
        ],
        "status": "planned", "provider": None, "model": None, "execution_mode": "not_started",
    } for role, key, deps in specs]

    dependencies = {key: set(deps) for _, key, deps in specs}
    completed: set[str] = set()
    waves: list[list[str]] = []
    while len(completed) < len(specs):
        ready = sorted(k for k, deps in dependencies.items() if k not in completed and deps <= completed)
        if not ready:
            raise EECPlanError("dependency cycle detected")
        waves.extend([ready[i:i + max_parallel_tasks] for i in range(0, len(ready), max_parallel_tasks)])
        completed.update(ready)

    plan = {
        "plan_id": plan_id, "eec_version": EEC_VERSION, "status": "planned",
        "task_kind": task_kind, "data_classification": data_classification,
        "objective_sha256": objective_hash, "objective": objective.strip(),
        "tasks": tasks, "execution_waves": waves,
        "policy": {
            "max_parallel_tasks": max_parallel_tasks, "max_spend": 0,
            "provider_calls_enabled": False, "external_data_transfer": False,
            "live_execution": False, "human_approval_required_for_side_effects": True,
            "production_access": False,
        },
        "execution_readiness": "blocked_pending_typed_worker_and_zero_cost_provider_gate",
        "disclaimer": "Plan only. No agents, models, tools, or external services were invoked.",
    }
    plan["plan_sha256"] = _digest(plan)
    return plan
