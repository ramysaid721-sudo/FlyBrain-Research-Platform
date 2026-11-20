"""Fail-closed component governance for FASE service emulation.

This module records engineering review evidence. It does not provide legal
advice, perform patent clearance, or determine infringement.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import re

REVIEW_STATES = {
    "unreviewed", "in_review", "approved", "approved_with_conditions",
    "rejected", "quarantined", "expired",
}
COMPONENT_TYPES = {
    "original", "open_source", "licensed_software", "hosted_api",
    "dataset", "model", "font_asset", "media_asset",
}
LICENCE_APPROVAL_STATES = {"approved", "approved_with_conditions"}
PATENT_STATES = {
    "not_assessed", "not_applicable", "reviewed_no_blocker",
    "counsel_review_required", "cleared_by_counsel",
}
TRADE_SECRET_STATES = {"not_assessed", "no_restricted_material", "counsel_review_required"}
TERMS_STATES = {"not_assessed", "approved", "approved_with_conditions", "prohibited"}
SECURITY_STATES = {"not_assessed", "passed", "conditional", "failed"}


@dataclass(frozen=True)
class ComponentReview:
    component_id: str
    component_type: str
    source_url: str | None
    licence_id: str | None
    provenance_verified: bool
    licence_review_status: str
    clean_room_required: bool
    clean_room_spec_approved: bool
    restricted_material_accessed: bool
    patent_review_required: bool
    patent_review_status: str
    trade_secret_review_status: str
    terms_review_status: str
    security_review_status: str
    intended_use: str
    jurisdiction: str


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def evaluate_component_review(record: dict[str, Any]) -> dict[str, Any]:
    """Evaluate recorded evidence; unknown or missing evidence fails closed."""
    if not isinstance(record, dict):
        raise ValueError("component review must be an object")

    required = {
        "component_id", "component_type", "provenance_verified",
        "licence_review_status", "clean_room_required",
        "clean_room_spec_approved", "restricted_material_accessed",
        "patent_review_required", "patent_review_status",
        "trade_secret_review_status", "terms_review_status",
        "security_review_status", "intended_use", "jurisdiction",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError("missing required review fields: " + ", ".join(missing))

    component_id = record["component_id"]
    if not _nonempty(component_id) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}", component_id):
        raise ValueError("component_id must be 2-128 safe identifier characters")
    component_type = record["component_type"]
    if component_type not in COMPONENT_TYPES:
        raise ValueError("unsupported component_type")
    for field in (
        "provenance_verified", "clean_room_required",
        "clean_room_spec_approved", "restricted_material_accessed",
        "patent_review_required",
    ):
        if not isinstance(record[field], bool):
            raise ValueError(field + " must be boolean")

    for field, allowed in (
        ("licence_review_status", REVIEW_STATES),
        ("patent_review_status", PATENT_STATES),
        ("trade_secret_review_status", TRADE_SECRET_STATES),
        ("terms_review_status", TERMS_STATES),
        ("security_review_status", SECURITY_STATES),
    ):
        if record[field] not in allowed:
            raise ValueError("invalid " + field)

    if not _nonempty(record["intended_use"]) or not _nonempty(record["jurisdiction"]):
        raise ValueError("intended_use and jurisdiction must be non-empty")

    if component_type != "original":
        if not _nonempty(record.get("source_url")):
            raise ValueError("third-party components require a source_url")
        if not _nonempty(record.get("licence_id")):
            raise ValueError("third-party components require a licence_id; unknown is not approval")
    if component_type in {"open_source", "licensed_software", "dataset", "model", "font_asset", "media_asset"}:
        if record["licence_review_status"] not in LICENCE_APPROVAL_STATES:
            pass

    review = ComponentReview(
        component_id=component_id,
        component_type=component_type,
        source_url=record.get("source_url"),
        licence_id=record.get("licence_id"),
        provenance_verified=record["provenance_verified"],
        licence_review_status=record["licence_review_status"],
        clean_room_required=record["clean_room_required"],
        clean_room_spec_approved=record["clean_room_spec_approved"],
        restricted_material_accessed=record["restricted_material_accessed"],
        patent_review_required=record["patent_review_required"],
        patent_review_status=record["patent_review_status"],
        trade_secret_review_status=record["trade_secret_review_status"],
        terms_review_status=record["terms_review_status"],
        security_review_status=record["security_review_status"],
        intended_use=record["intended_use"],
        jurisdiction=record["jurisdiction"],
    )

    blockers: list[str] = []
    if not review.provenance_verified:
        blockers.append("source provenance is not verified")
    if review.component_type != "original" and review.licence_review_status not in LICENCE_APPROVAL_STATES:
        blockers.append("third-party licence review is not approved")
    if review.clean_room_required and not review.clean_room_spec_approved:
        blockers.append("clean-room specification has not been independently approved")
    if review.restricted_material_accessed:
        blockers.append("restricted or confidential material may have influenced the implementation")
    if review.patent_review_required and review.patent_review_status != "cleared_by_counsel":
        blockers.append("material patent concern requires qualified counsel clearance")
    if review.patent_review_status == "counsel_review_required":
        blockers.append("patent review is awaiting qualified counsel")
    if review.trade_secret_review_status != "no_restricted_material":
        blockers.append("trade-secret review is unresolved or requires counsel")
    if review.terms_review_status not in {"approved", "approved_with_conditions"}:
        blockers.append("API or service terms review is not approved")
    if review.security_review_status not in {"passed", "conditional"}:
        blockers.append("security review has not passed")
    if review.licence_review_status == "approved_with_conditions" or review.terms_review_status == "approved_with_conditions" or review.security_review_status == "conditional":
        blockers.append("approval conditions must be explicitly enforced before activation")

    return {
        "component_id": review.component_id,
        "decision": "blocked" if blockers else "eligible_for_human_approval",
        "release_eligible": not blockers,
        "blockers": blockers,
        "review_record": asdict(review),
        "legal_boundary": (
            "Engineering evidence gate only; not legal advice, patent clearance, "
            "or a determination that a use is non-infringing."
        ),
    }
