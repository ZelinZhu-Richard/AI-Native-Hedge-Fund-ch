from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    CompanyAlias,
    CompanyAliasKind,
    DocumentEntityLink,
    DocumentEntityLinkScope,
    EntityReference,
    ResolutionConfidence,
    ResolutionConflict,
    ResolutionConflictKind,
    ResolutionDecision,
    ResolutionDecisionStatus,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)


def test_entity_reference_wraps_canonical_company_identity() -> None:
    entity_reference = EntityReference(
        entity_reference_id="eref_test",
        company_id="co_apex",
        legal_name="Apex Instruments, Inc.",
        canonical_ticker="APEX",
        exchange="NASDAQ",
        cik="0001983210",
        active=True,
        company_alias_ids=["calias_test"],
        ticker_alias_ids=["talias_test"],
        cross_source_link_ids=["xsrc_test"],
        latest_resolution_decision_id="rdec_test",
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert entity_reference.entity_kind == "company"
    assert entity_reference.company_id == "co_apex"


def test_company_alias_rejects_inverted_validity_window() -> None:
    with pytest.raises(ValidationError, match="valid_to must be greater than or equal to valid_from"):
        CompanyAlias(
            company_alias_id="calias_test",
            company_id="co_apex",
            alias_text="Apex Instrument Systems, Inc.",
            alias_kind=CompanyAliasKind.FORMER_NAME,
            valid_from=FIXED_NOW,
            valid_to=FIXED_NOW.replace(hour=9),
            confidence=ResolutionConfidence.HIGH,
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_document_entity_link_requires_evidence_spans_for_inherited_scope() -> None:
    with pytest.raises(ValidationError, match="evidence_inherited links must reference at least one evidence span"):
        DocumentEntityLink(
            document_entity_link_id="dlink_test",
            document_id="doc_test",
            source_reference_id="src_test",
            company_id="co_apex",
            entity_reference_id="eref_test",
            link_scope=DocumentEntityLinkScope.EVIDENCE_INHERITED,
            resolution_decision_id="rdec_test",
            confidence=ResolutionConfidence.HIGH,
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_resolution_conflict_requires_multiple_candidates_for_alias_collision() -> None:
    with pytest.raises(ValidationError, match="Multiple-candidate conflicts must include at least two candidates"):
        ResolutionConflict(
            resolution_conflict_id="rconf_test",
            target_type="document",
            target_id="doc_test",
            conflict_kind=ResolutionConflictKind.ALIAS_COLLISION,
            candidate_company_ids=["co_apex"],
            message="Ambiguous alias.",
            blocking=True,
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_resolution_decision_enforces_ambiguous_and_unresolved_states() -> None:
    with pytest.raises(ValidationError, match="Ambiguous decisions must use ambiguous confidence"):
        ResolutionDecision(
            resolution_decision_id="rdec_ambiguous",
            target_type="document",
            target_id="doc_test",
            candidate_company_ids=["co_apex", "co_other"],
            selected_company_id=None,
            status=ResolutionDecisionStatus.AMBIGUOUS,
            confidence=ResolutionConfidence.MEDIUM,
            rule_name="headline_alias_unique_ambiguous",
            rationale="Two aliases matched.",
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )

    with pytest.raises(ValidationError, match="Unresolved decisions must use unresolved confidence"):
        ResolutionDecision(
            resolution_decision_id="rdec_unresolved",
            target_type="document",
            target_id="doc_test",
            candidate_company_ids=[],
            selected_company_id=None,
            status=ResolutionDecisionStatus.UNRESOLVED,
            confidence=ResolutionConfidence.LOW,
            rule_name="no_document_entity_match",
            rationale="Nothing matched.",
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
