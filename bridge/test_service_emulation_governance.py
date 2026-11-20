import pytest

from flybrain_os.service_emulation_governance import evaluate_component_review


def base_record(**overrides):
    record = {
        "component_id": "flybrain.native.storage",
        "component_type": "original",
        "source_url": None,
        "licence_id": None,
        "provenance_verified": True,
        "licence_review_status": "unreviewed",
        "clean_room_required": False,
        "clean_room_spec_approved": False,
        "restricted_material_accessed": False,
        "patent_review_required": False,
        "patent_review_status": "not_assessed",
        "trade_secret_review_status": "no_restricted_material",
        "terms_review_status": "approved",
        "security_review_status": "passed",
        "intended_use": "staging-only",
        "jurisdiction": "deployment jurisdiction to be confirmed",
    }
    record.update(overrides)
    return record


def test_original_component_can_be_eligible_with_verified_provenance():
    result = evaluate_component_review(base_record())
    assert result["decision"] == "eligible_for_human_approval"
    assert result["release_eligible"] is True
    assert result["blockers"] == []


def test_unknown_third_party_licence_is_rejected():
    with pytest.raises(ValueError):
        evaluate_component_review(base_record(
            component_type="open_source",
            source_url="https://example.org/project",
            licence_id="NOASSERTION",
            licence_review_status="approved",
        ))


def test_third_party_component_requires_licence_review():
    result = evaluate_component_review(base_record(
        component_type="open_source",
        source_url="https://example.org/project",
        licence_id="MIT",
    ))
    assert result["decision"] == "blocked"
    assert any("licence review" in item for item in result["blockers"])


def test_approved_third_party_component_can_be_eligible_for_human_approval():
    result = evaluate_component_review(base_record(
        component_type="open_source",
        source_url="https://example.org/project",
        licence_id="MIT",
        licence_review_status="approved",
    ))
    assert result["decision"] == "eligible_for_human_approval"


def test_unverified_provenance_blocks_component():
    result = evaluate_component_review(base_record(provenance_verified=False))
    assert result["release_eligible"] is False
    assert any("provenance" in item for item in result["blockers"])


def test_clean_room_spec_must_be_approved_when_required():
    result = evaluate_component_review(base_record(clean_room_required=True))
    assert result["decision"] == "blocked"
    assert any("clean-room" in item for item in result["blockers"])


def test_restricted_material_access_blocks_implementation():
    result = evaluate_component_review(base_record(restricted_material_accessed=True))
    assert result["decision"] == "blocked"
    assert any("restricted" in item for item in result["blockers"])


def test_material_patent_concern_requires_counsel_clearance():
    result = evaluate_component_review(base_record(
        patent_review_required=True,
        patent_review_status="reviewed_no_blocker",
    ))
    assert result["decision"] == "blocked"
    assert any("patent" in item for item in result["blockers"])


def test_patent_clearance_is_not_inferred_from_code_rewrite():
    result = evaluate_component_review(base_record(
        patent_review_required=True,
        patent_review_status="not_assessed",
    ))
    assert result["release_eligible"] is False


def test_unapproved_terms_or_security_review_blocks():
    result = evaluate_component_review(base_record(
        terms_review_status="not_assessed",
        security_review_status="not_assessed",
    ))
    assert result["decision"] == "blocked"
    assert len(result["blockers"]) >= 2


def test_conditional_approval_requires_conditions_to_be_enforced_before_activation():
    result = evaluate_component_review(base_record(security_review_status="conditional"))
    assert result["decision"] == "blocked"
    assert any("conditions" in item for item in result["blockers"])


def test_invalid_or_missing_fields_are_rejected():
    with pytest.raises(ValueError):
        evaluate_component_review({"component_id": "incomplete"})
    with pytest.raises(ValueError):
        evaluate_component_review(base_record(provenance_verified="yes"))
