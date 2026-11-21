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

## Current verified state — 2026-11-20

- GitHub staging workflow exists at `.github/workflows/autonomous-cloud-factory.yml` and now partitions the five targeted test files into three parallel shards (maximum parallelism 3).
- GitHub expanded all three matrix jobs, but hosted-runner allocation failed before the first workflow step: runner_id=0 or null, empty runner_name, and zero steps. A targeted rerun reproduced the same infrastructure failure. No pytest failure is inferred from these runs.
- The same three test shards were executed concurrently in the existing Vercel staging Sandbox on Python 3.14.4: 35 + 22 + 17 = 74 passed, zero failed. Bridge overlay and compileall passed. Python 3.12 compatibility remains unverified.
- Supabase Free project `forge-ai-db` (ref `zjhzfjzadrpsbfphxgjw`) has the RLS-enabled mission schema, deployed `flybrain-control` Edge Function (version 5), Vault-backed worker credentials, pg_net, and an active pg_cron dispatcher.
- Cron job `flybrain-worker-dispatch-every-five-minutes` is active at `*/5 * * * *`. The staging Vercel trigger URL in Vault points to the latest verified staging Preview deployment.
- The Vercel worker uses a persistent named Sandbox snapshot, but individual sessions stop after bounded work. The sandbox is not a continuously running VM.
- Task 6 (checkpoint persistence and idempotent side-effect prevention) is VERIFIED. Independent ledger inspection confirmed one side-effect row across an interrupted execution and its resumed retry.
- Task 8 (scheduled continuity qualification) is VERIFIED. A first worker saved phase 1 and stopped; after lease expiry, Supabase Cron dispatched a second execution, which resumed from the durable checkpoint and completed phase 2. The second dispatch required no ChatGPT tool call. The ChatGPT conversation itself was not closed, and a scheduler-process restart was not simulated.
- Task 9 (external release bridge qualification) remains AWAITING_VERIFICATION because Python 3.12 compatibility has not been independently confirmed.
- Task 7 (autonomous reasoning model) remains WAITING_APPROVAL because no model endpoint, credentials, data-sharing policy, and spending ceiling have been approved.
- Other foundational tasks 1–5 are VERIFIED.
- Latest deployments were staging Preview deployments only. Production was not modified.
- Additional compute providers are not yet active: Railway has zero projects; Render has a workspace but no workspace was selected for operations; no Cloudflare connector is available in this execution environment; TinyFish has a negative wallet balance and is not used.
- The system is therefore capable of scheduled, durable worker recovery for the tested task path, but it is not yet a fully qualified multi-cloud worker pool or a model-backed autonomous engineering system.
