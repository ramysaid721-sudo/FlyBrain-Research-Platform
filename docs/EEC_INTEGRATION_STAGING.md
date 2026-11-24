# EEC Integration — FlyBrain Staging

**Status:** Initial executable planning layer added on an isolated Staging branch. This is not a live multi-provider runtime.

## Existing components reused

- FlyBrain-NOS ModelHub remains the provider abstraction; no second model registry is introduced.
- URCAL remains the compute and queue policy layer; no competing queue is introduced.
- Supabase PGMQ, task groups, task ledger, lease fencing, idempotency, and capability tokens remain the durable task foundation.
- The existing Vercel MCP bridge remains the public interface.
- The existing multi-agent dry-run proof remains a separate deterministic validation artifact.

## EEC responsibilities

The EEC layer supplies bounded task decomposition, role assignment, dependency graphs, execution waves, acceptance criteria, and a deterministic plan hash. Roles include strategic planning, research, architecture, engineering, security, QA, code review, performance, documentation, and synthesis.

## Safety and cost gates

- Hard maximum spend: zero.
- Live provider inference: disabled.
- External data transfer: disabled.
- Default data classification: internal.
- Confidential and prohibited data never enter an external provider route.
- The planning endpoint does not execute tools, install packages, invoke models, or write to the source repository. The authenticated submission tool writes only plan hashes, role/task metadata, and dependency IDs to the Staging ledger.
- Side effects require human approval.
- Production access is excluded.

## Execution model

Plans are represented as a dependency graph and partitioned into bounded waves. Independent tasks may share a wave; dependent tasks cannot. Parallelism is capped at four. The planner does not claim that a planned task has run.

## Staging database foundation

Applied and verified on the existing free-tier Staging Supabase project:
- Migration 20261124131058 creates private run, task, attempt, and event ledgers.
- Migration 20261124131109 adds the task-event lookup index.
- Migration 20261124131126 removes DELETE permission from the service role to preserve the audit history.
- All four tables have RLS enabled; anon and authenticated have no SELECT access; service_role has the required operational permissions.
- Spend is constrained to exactly zero and external data transfer to false at the database level.
- The ledger stores hashes and policy metadata, not raw objectives, prompts, or credentials.

The existing worker still handles only research_search. The ledger now includes a private artifact store, deferred same-run dependency validation, and service-role-only RPCs for idempotent plan persistence and plan-status retrieval. A nine-task engineering plan for this integration has been persisted and read back successfully. The plan is stored as hashes, role/task metadata, and dependency IDs; the raw objective is not stored. An authenticated Staging Edge Function (`flybrain-eec-ledger`) exposes plan persistence and status readback using a dedicated Staging-only credential held in Supabase Vault and a branch-scoped Vercel Preview environment variable. A per-IP database rate limit protects the endpoint. The MCP bridge now includes authenticated `eec_submit_plan` and `eec_plan_status` tools; `eec_plan` remains read-only. This connects the planner to durable persistence, but not yet to a task-claim/execute worker, and no EEC agent execution has been activated.

## Deployment boundary

Vercel automatically generated a Preview deployment for the pull request. No Production deployment or merge was performed.

## Remaining implementation gates

1. Connect the typed EEC task contract to URCAL using the existing queue, lease fencing, and idempotency primitives.
2. Add worker-side claim, heartbeat, completion, retry, and artifact-writing operations for EEC task records.
3. Add independent review and QA result gates so synthesis cannot accept unreviewed work.
4. Inspect and extend the existing packaged ModelHub adapter contract without creating a second provider registry.
5. Verify provider-specific zero-cost evidence before any live provider request. If unavailable, retain mock-only execution.
6. Verify the full Staging path end-to-end, then keep Production entirely separate.

## Acceptance criteria

- Unit tests cover input validation, task dependencies, bounded parallelism, policy defaults, and plan hashing.
- MCP exposes read-only eec_status, eec_plan, and eec_plan_status, plus authenticated eec_submit_plan for durable plan persistence.
- Existing MCP, queue, and research behavior remains unchanged.
- No live inference, external transfer, billing, Production changes, or deployment occurs in this phase.
