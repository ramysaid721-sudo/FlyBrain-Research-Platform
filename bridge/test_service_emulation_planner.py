import pytest

from flybrain_os.service_emulation_planner import plan_service_emulation


def candidate(**overrides):
    value = {
        "candidate_id": "native.search.v1",
        "capability": "search",
        "implementation_type": "original",
        "review_status": "approved",
        "licence_status": "approved",
        "provenance_verified": True,
        "terms_status": "approved",
        "security_status": "passed",
        "cost_state": "known_zero",
        "estimated_monthly_cost": 0,
        "supports_requirements": ["full_text", "filters"],
        "data_classes": ["public", "internal"],
        "deployment_modes": ["self_hosted"],
        "operationally_verified": True,
    }
    value.update(overrides)
    return value


def request(candidates, **overrides):
    value = {
        "capability": "search",
        "required_features": ["full_text"],
        "data_classification": "public",
        "deployment_mode": "self_hosted",
        "candidates": candidates,
    }
    value.update(overrides)
    return value


def test_selects_only_approved_operational_zero_cost_candidate():
    result = plan_service_emulation(request([candidate()]))
    assert result["status"] == "candidate_selected"
    assert result["selected_candidate"]["candidate_id"] == "native.search.v1"
    assert result["execution_performed"] is False
    assert result["activation_performed"] is False


def test_unknown_cost_fails_closed():
    result = plan_service_emulation(request([candidate(cost_state="unknown")]))
    assert result["status"] == "no_eligible_candidate"
    assert "cost is unknown" in result["rejected_candidates"][0]["blockers"]


def test_paid_candidate_requires_explicit_permission():
    paid = candidate(candidate_id="hosted.search", implementation_type="hosted_api",
                     cost_state="known_nonzero", estimated_monthly_cost=5)
    assert plan_service_emulation(request([paid]))["status"] == "no_eligible_candidate"
    result = plan_service_emulation(request([paid], allow_paid=True))
    assert result["status"] == "candidate_selected"


def test_unreviewed_or_unverified_candidates_are_rejected():
    result = plan_service_emulation(request([candidate(review_status="unreviewed")]))
    assert result["status"] == "no_eligible_candidate"
    result = plan_service_emulation(request([candidate(provenance_verified=False)]))
    assert result["status"] == "no_eligible_candidate"


def test_data_classification_and_deployment_mode_are_enforced():
    result = plan_service_emulation(request([candidate(data_classes=["public"])],
                                             data_classification="confidential"))
    assert result["status"] == "no_eligible_candidate"
    result = plan_service_emulation(request([candidate(deployment_modes=["hosted"]) ]))
    assert result["status"] == "no_eligible_candidate"


def test_required_features_must_be_supported():
    result = plan_service_emulation(request([candidate(supports_requirements=["filters"])]))
    assert result["status"] == "no_eligible_candidate"
    assert any("missing required features" in item for item in result["rejected_candidates"][0]["blockers"])


def test_zero_cost_claim_must_have_zero_estimate():
    result = plan_service_emulation(request([candidate(estimated_monthly_cost=1)]))
    assert result["status"] == "no_eligible_candidate"


def test_invalid_requests_are_rejected():
    with pytest.raises(ValueError):
        plan_service_emulation({"capability": "search"})
    with pytest.raises(ValueError):
        plan_service_emulation(request([], allow_paid="yes"))
