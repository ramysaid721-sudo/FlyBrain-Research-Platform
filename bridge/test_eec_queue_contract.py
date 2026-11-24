import uuid
import pytest

try:
    from flybrain_os.eec_queue_contract import (
        EECQueueContractError, build_queue_message, build_queue_ledger_payload,
        validate_claim, dependencies_satisfied,
    )
except ImportError:
    from bridge.eec_queue_contract import (
        EECQueueContractError, build_queue_message, build_queue_ledger_payload,
        validate_claim, dependencies_satisfied,
    )


def uid():
    return str(uuid.uuid4())


def test_queue_message_contains_only_task_id():
    task_id = uid()
    assert build_queue_message(task_id) == {"task_id": task_id}


def test_queue_ledger_payload_contains_only_run_and_task_ids():
    run_id, task_id = uid(), uid()
    assert build_queue_ledger_payload(run_id, task_id) == {
        "run_id": run_id, "task_id": task_id
    }


def test_claim_requires_typed_task_and_exact_identifier_payload():
    run_id, task_id, claim_token = uid(), uid(), uid()
    claim = {
        "task_type": "eec_agent", "task_id": task_id, "message_id": 42,
        "claim_token": claim_token,
        "payload": {"run_id": run_id, "task_id": task_id},
    }
    assert validate_claim(claim) == (run_id, task_id, claim_token)


@pytest.mark.parametrize("mutate", [
    lambda c: c.update(task_type="research_search"),
    lambda c: c.update(payload={"run_id": uid(), "task_id": uid(), "objective": "secret"}),
    lambda c: c.update(payload={"run_id": uid()}),
    lambda c: c.update(task_id=uid()),
    lambda c: c.update(claim_token="not-a-uuid"),
    lambda c: c.update(message_id=0),
])
def test_claim_rejects_malformed_or_overloaded_payload(mutate):
    run_id, task_id, claim_token = uid(), uid(), uid()
    claim = {
        "task_type": "eec_agent", "task_id": task_id, "message_id": 42,
        "claim_token": claim_token,
        "payload": {"run_id": run_id, "task_id": task_id},
    }
    mutate(claim)
    with pytest.raises(EECQueueContractError):
        validate_claim(claim)


def test_invalid_uuid_is_rejected_before_enqueue_contract():
    with pytest.raises(EECQueueContractError):
        build_queue_message("not-a-uuid")
    with pytest.raises(EECQueueContractError):
        build_queue_ledger_payload(uid(), "not-a-uuid")


def test_ordinary_dependency_may_start_after_completed():
    assert dependencies_satisfied("software_engineer", ["completed", "accepted"])
    assert not dependencies_satisfied("software_engineer", ["running"])


def test_synthesis_waits_for_review_or_acceptance():
    assert dependencies_satisfied("synthesizer", ["reviewed", "accepted"])
    assert not dependencies_satisfied("synthesizer", ["completed"])
    assert dependencies_satisfied("synthesizer", [])


def test_dependency_gate_fails_closed_for_invalid_input():
    assert not dependencies_satisfied(None, [])
    assert not dependencies_satisfied("research_specialist", "completed")
    assert not dependencies_satisfied("research_specialist", [None])
