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
- No tool execution, package installation, repository writes, or deployments are performed by the planning endpoint.
- Side effects require human approval.
- Production access is excluded.

## Execution model

Plans are represented as a dependency graph and partitioned into bounded waves. Independent tasks may share a wave; dependent tasks cannot. Parallelism is capped at four. The planner does not claim that a planned task has run.

## Remaining implementation gates

1. Inspect and extend the existing packaged ModelHub adapter contract without creating a second provider registry.
2. Add durable agent-attempt and artifact records to the existing Staging ledger after migration and RLS review.
3. Adapt the existing URCAL worker to claim typed agent tasks and enforce lease fencing/idempotency.
4. Add independent review and QA result gates.
5. Verify provider-specific zero-cost evidence before any live provider request. If unavailable, retain mock-only execution.
6. Verify Staging end-to-end, then keep Production entirely separate.

## Acceptance criteria

- Unit tests cover input validation, task dependencies, bounded parallelism, policy defaults, and plan hashing.
- MCP exposes read-only eec_status and eec_plan.
- Existing MCP, queue, and research behavior remains unchanged.
- No live inference, external transfer, billing, Production changes, or deployment occurs in this phase.
