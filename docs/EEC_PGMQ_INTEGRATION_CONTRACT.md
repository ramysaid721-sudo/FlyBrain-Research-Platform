# EEC ↔ PGMQ Integration Contract (Design + Unit-Tested Envelope)

**State: contract implementation only. Not enqueued, not deployed, and not a live worker.**

## Architecture boundary

- PGMQ remains the single task transport already used by FlyBrain/URCAL.
- `private.flybrain_agent_runs` and `private.flybrain_agent_tasks` remain the authoritative EEC orchestration ledger.
- `public.flybrain_task_runs` remains the transport/worker lease ledger.
- An EEC task ID is the stable correlation identifier across the EEC task row and the PGMQ transport row. The enqueue operation must reject any ID collision or mismatched run/task relationship.
- No second queue, provider registry, or task scheduler is introduced.

## Message and payload contract

The PGMQ message body is exactly:

```json
{"task_id":"<EEC task UUID>"}
```

The matching `flybrain_task_runs.payload` is exactly:

```json
{"run_id":"<EEC run UUID>","task_id":"<EEC task UUID>"}
```

No objective, prompt, task instruction, input content, credentials, artifact body, provider name, or model name may enter either envelope. The task type is `eec_agent` in the queue ledger; the existing claim RPC obtains that type from the ledger row.

The current reference contract code validates exact key sets, UUIDs, message IDs, claim-token presence, and equality between the queue task ID and EEC task ID. It is not connected to the database yet.

## Claim and lease transaction

The future migration must extend the existing `flybrain_claim_task` transaction—not add a competing claim RPC path—to:
1. Read and validate the PGMQ message and lock the matching `flybrain_task_runs` row.
2. Verify `task_type = eec_agent`, then lock the EEC task and run rows.
3. Verify run/task relationship, run policy gates, task status, attempt ceiling, and dependency readiness.
4. Generate one fresh lease token and set the same token and expiry in both ledgers.
5. Increment both attempt counters and append a sanitized EEC attempt/event record atomically.
6. Return only IDs, task type, lease metadata, and policy metadata needed by the typed worker—not the objective or private task input.

If any step fails, the transaction must roll back both ledgers. A blocked dependency must be deferred without incrementing an execution attempt.

## Heartbeat, completion, failure, and retry

All state transitions must verify all of:
- queue task ID and PGMQ message ID;
- EEC run ID and EEC task ID;
- the same lease token in both ledgers;
- `status = running` in both ledgers;
- unexpired lease in both ledgers.

Heartbeat must extend both expirations and the PGMQ visibility timeout atomically. Completion must write an artifact with a verified SHA-256, update both task rows, append events, and archive the PGMQ message in one transaction. Failure/retry must use bounded attempts, bounded backoff, and the same lease fencing. A stale worker must be unable to complete, fail, or heartbeat after lease expiry or reassignment.

## Dependency and independent-review gates

- Ordinary tasks may be claimed only when every dependency is `completed`, `reviewed`, or `accepted`.
- The `synthesizer` may be claimed only when every dependency is `reviewed` or `accepted`; `completed` alone is insufficient.
- A review task must be a separate task and must not approve its own output.
- Run completion requires all mandatory review and QA tasks to be accepted; partial completion must not mark the run complete.

The pure dependency-gate contract is unit-tested in `bridge/test_eec_queue_contract.py`.

## Input materialization is a separate mandatory gate

The present EEC task schema stores `input_sha256`, not the task's input content. This is intentionally data-minimizing but insufficient for execution. Before a worker can perform any task, a separately authorized internal input-materialization design must:
- store or reference task-specific instructions in a private, access-controlled source;
- enforce the run's `data_classification` and deny prohibited inputs;
- verify the fetched content against `input_sha256`;
- avoid logging or returning raw inputs in queue messages, ordinary events, or error messages;
- prohibit external provider transfer while the zero-cost and provider policy gates are closed.

Until this is designed and tested, no EEC task is executable. Do not fabricate task inputs from hashes or reconstruct them from the original objective.

## Policy gates (fail closed)

- `max_spend_usd = 0`
- `external_data_transfer = false`
- `provider_calls_enabled = false`
- `live_execution = false`
- `production_access = false`

These gates must be checked inside the enqueue and claim database transactions, not only in application code. The current nine-task engineering plan remains `planned` and must not be enqueued by this integration work.

## Migration sequence

1. Add a constrained `eec_agent` task type and exact payload validation without changing `research_search` behavior.
2. Add a service-role-only, idempotent enqueue RPC that checks run/task membership and policy, then inserts both ledger rows and the PGMQ message atomically.
3. Extend claim/heartbeat/complete/fail/defer RPCs with dual-ledger lease fencing and rollback guarantees.
4. Add a typed worker dispatch branch for `eec_agent`; preserve the existing Crossref branch unchanged.
5. Add database integration tests for duplicate enqueue, mismatched run/task IDs, blocked dependencies, stale leases, concurrent claims, retry exhaustion, artifact hash mismatch, and atomic rollback.
6. Run a separate synthetic plan through the entire mock-only lifecycle. Never mutate or enqueue the existing engineering plan.

No database migration or worker deployment is authorized by this design document alone.
