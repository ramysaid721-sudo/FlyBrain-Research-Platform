import pytest

from groq_free_admission import evaluate_groq_admission


MODEL = "explicitly-approved-free-model"


def evidence(**overrides):
    data = {
        "model_id": MODEL,
        "captured_at": 1_000.0,
        "source": "https://api.groq.com/openai/v1/models",
        "input_cost_per_million": 0,
        "output_cost_per_million": 0,
        "remaining_requests": 10,
        "remaining_tokens": 10_000,
        "free_quota_confirmed": True,
    }
    data.update(overrides)
    return data


def decide(data, *, model=MODEL, now=1_050.0):
    return evaluate_groq_admission(
        data,
        requested_model=model,
        allowlisted_models={MODEL},
        now_epoch=now,
    )


def test_accepts_fresh_explicit_zero_cost_evidence():
    result = decide(evidence())
    assert result.allowed is True
    assert result.reason == "zero_cost_and_fresh_quota_verified"


def test_rejects_missing_evidence():
    assert decide(None).reason == "pricing_quota_evidence_missing"


def test_rejects_model_not_allowlisted():
    assert decide(evidence(), model="another-model").reason == "model_not_allowlisted"


def test_rejects_model_mismatch():
    assert decide(evidence(model_id="different-model")).reason == "evidence_model_mismatch"


@pytest.mark.parametrize("field", ["input_cost_per_million", "output_cost_per_million"])
def test_rejects_any_positive_price(field):
    assert decide(evidence(**{field: 0.01})).reason == "nonzero_or_unknown_model_price"


def test_rejects_unknown_price():
    assert decide(evidence(input_cost_per_million=None)).reason == "malformed_pricing_quota_evidence"


def test_rejects_stale_evidence():
    assert decide(evidence(captured_at=800.0)).reason == "pricing_quota_evidence_stale"


def test_rejects_future_evidence_timestamp():
    assert decide(evidence(captured_at=1_051.0)).reason == "pricing_quota_evidence_stale"


def test_rejects_empty_quota():
    assert decide(evidence(remaining_requests=0)).reason == "free_quota_exhausted_or_unknown"
    assert decide(evidence(remaining_tokens=0)).reason == "free_quota_exhausted_or_unknown"


def test_rejects_unconfirmed_free_quota():
    assert decide(evidence(free_quota_confirmed=False)).reason == "free_quota_not_confirmed"


def test_rejects_non_https_evidence_source():
    assert decide(evidence(source="http://example.invalid")).reason == "untrusted_evidence_source"


def test_rejects_incomplete_evidence():
    data = evidence()
    del data["remaining_tokens"]
    assert decide(data).reason == "pricing_quota_evidence_incomplete"
