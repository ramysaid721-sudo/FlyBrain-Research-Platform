# FlyBrain Autonomous Continuity Control Plane

Status: architecture baseline; implementation is partial and must not be represented as an operational autonomous agent.

## Objective
Move durable project state, task execution, retries, checkpoints, and audit evidence out of ChatGPT conversations. ChatGPT remains an optional supervisory interface. The FlyBrain control plane must continue deterministic, pre-authorized work when no ChatGPT session is active.

## Operating model
1. A durable mission ledger stores the project goal, approved scope, task graph, dependencies, current task state, checkpoints, retry counts, artifact references, and evidence.
2. A scheduler claims ready tasks using expiring leases. A task may be claimed by only one worker at a time.
3. Workers execute isolated, bounded tasks in external compute. They report structured results and immutable logs to the ledger.
4. A verifier checks task acceptance criteria independently of the worker that performed the task.
5. A recovery controller retries transient failures with bounded exponential backoff, quarantines repeated failures, and resumes from the last verified checkpoint.
6. A supervisor dashboard exposes progress, blockers, spend, quota consumption, and approvals. ChatGPT can inspect and direct this system when connected, but is not the system's persistent memory or scheduler.

## Required task record
Each task must contain stable task_id and idempotency_key; objective, scope, dependencies, and acceptance_tests; data_classification and allowed_network_domains; worker_type, resource_budget, timeout, and retry_limit; allowed_actions and prohibited_actions; status, lease_owner, lease_expiry, attempt_count; checkpoint_uri, artifact_uris, test_evidence, and timestamps.

## State machine
queued -> ready -> leased -> running -> verifying -> completed
Transient failure: running -> retry_wait -> ready.
Exhausted retries: running -> quarantined.
Failed verification: verifying -> retry_wait or quarantined.
Cancellation: queued, ready, or retry_wait -> cancelled.
No worker may mark its own task completed without independent acceptance evidence.

## Execution topology
- Control plane: durable scheduler, task API, policy engine, audit log, and watchdog.
- Worker plane: ephemeral isolated runners for builds, tests, code analysis, and approved edits.
- Storage plane: artifact store with immutable/versioned outputs and content hashes.
- Observability plane: task traces, logs, metrics, quota accounting, and failure alerts.
- Supervisory plane: ChatGPT interface for planning, review, and exception handling.

## Continuity rules
- No task state may exist only in conversation history or a worker's ephemeral filesystem.
- Every task writes a checkpoint before yielding or exiting.
- Long missions are split into resumable tasks with explicit dependencies, not into chat turns.
- Workers must be idempotent or use idempotency keys before mutating external state.
- A watchdog reclaims expired leases and restarts eligible tasks.
- Every deployment candidate is built and tested on staging; production promotion remains a separate approval gate.

## Autonomy policy
Allowed without per-task approval: repository inspection, static analysis, test execution, local code generation, and edits on the designated staging branch; bounded retries, log collection, issue triage, and preview artifacts; approved open-source dependencies after license/security review; backup and versioned artifact creation within verified free quotas.
Approval required: paid resources, overage, plan upgrades, quota increases; secrets, OAuth grants, new account creation, or broader permissions; production deployment, destructive changes, data deletion, or irreversible external actions; use of confidential/private project data with an external model or service.

## Model execution is a separate dependency
A task orchestrator can continue deterministic jobs without an LLM. Autonomous reasoning and code repair require a model endpoint and credentials. ChatGPT subscription access does not itself provide a perpetual background API runtime. Until a model provider and budget are explicitly configured, the system must restrict itself to deterministic automation, rule-based remediation, and queued tasks requiring supervisory review.

## Initial implementation sequence
1. Repair and validate the external runner allocation path. The first GitHub Actions Factory run failed before its first step: runner_id=0, runner_name empty, labels=[ubuntu-latest], and no steps. This is an infrastructure/startup failure, not evidence that Python tests failed.
2. Add a durable task ledger and transactional task-claim/lease API, preferably in an existing approved database or a Cloudflare durable service after checking quotas and permissions.
3. Add a watchdog/scheduler and bounded retry policy.
4. Add an external worker adapter with ephemeral execution, strict resource limits, and artifact upload.
5. Add independent acceptance verification and resumable checkpoints.
6. Add model-backed planning/repair only after the model endpoint, data policy, and cost ceiling are explicitly established.
7. Run end-to-end continuity tests: close the ChatGPT session, interrupt a worker, restart the scheduler, and verify that the mission resumes without duplicate side effects.

## Current verified state
- GitHub staging workflow exists at .github/workflows/autonomous-cloud-factory.yml.
- The workflow's first run failed before any step; GitHub reported runner_id=0, empty runner_name, and an empty steps array.
- Therefore, the build/test sequence has not run and no test pass is claimed.
- Vercel Preview deployment and health checks have succeeded previously, but that proves only the existing service build/health path, not the control plane.
- An existing Supabase Free project (`forge-ai-db`, ref `zjhzfjzadrpsbfphxgjw`) already contains an RLS-enabled mission schema: organizations, projects, tasks, executions, checkpoints, verification_evidence, approval_requests, and audit_events. Security advisors returned no lints at inspection time.
- A FlyBrain / URCAL mission project and eight durable tasks were seeded in that database. The first task is READY; seven are PLANNED or WAITING_APPROVAL. Two failed GitHub runner attempts and their external-check evidence were recorded. The model endpoint task is WAITING_APPROVAL because provider credentials and a hard cost ceiling are not configured.
- The database has no pg_cron, pg_net, or pgmq extensions enabled at inspection time, and no Edge Functions deployed. Thus the scheduler, watchdog, worker adapter, and external model-backed repair loop are not operational yet.