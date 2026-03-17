from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    ConfidenceAssessment,
    CounterHypothesis,
    CritiqueKind,
    EvidenceLinkRole,
    Hypothesis,
    HypothesisStatus,
    ProvenanceRecord,
    ResearchBrief,
    ResearchReviewStatus,
    ResearchStance,
    SupportingEvidenceLink,
)

FIXED_NOW = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)


def test_hypothesis_requires_supporting_links() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            hypothesis_id="hyp_test",
            company_id="co_test",
            title="Invalid Hypothesis",
            thesis="This should fail because no evidence links are attached.",
            stance=ResearchStance.POSITIVE,
            status=HypothesisStatus.UNDER_REVIEW,
            review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
            time_horizon="next_2_4_quarters",
            invalidation_conditions=["Guidance is lowered."],
            supporting_evidence_links=[],
            assumptions=["Demand remains stable."],
            uncertainties=["Evidence is management-sourced."],
            validation_steps=["Check the next earnings update."],
            confidence=_confidence(),
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_counter_hypothesis_requires_concrete_critique_basis() -> None:
    with pytest.raises(ValidationError):
        CounterHypothesis(
            counter_hypothesis_id="chyp_test",
            hypothesis_id="hyp_test",
            title="Invalid Counter",
            thesis="This should fail because it contains no actual critique content.",
            critique_kinds=[CritiqueKind.MISSING_EVIDENCE],
            supporting_evidence_links=[],
            challenged_assumptions=[],
            missing_evidence=[],
            causal_gaps=[],
            unresolved_questions=[],
            review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
            confidence=_confidence(),
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_research_brief_requires_next_validation_steps() -> None:
    with pytest.raises(ValidationError):
        ResearchBrief(
            research_brief_id="rbrief_test",
            company_id="co_test",
            title="Invalid Brief",
            context_summary="Context exists.",
            core_hypothesis="Core hypothesis exists.",
            counter_hypothesis_summary="Counter summary exists.",
            hypothesis_id="hyp_test",
            counter_hypothesis_id="chyp_test",
            evidence_assessment_id="eass_test",
            supporting_evidence_links=[_supporting_link()],
            key_counterarguments=["Adoption is still unproven."],
            confidence=_confidence(),
            uncertainty_summary="Evidence is incomplete.",
            review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
            next_validation_steps=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def _supporting_link() -> SupportingEvidenceLink:
    return SupportingEvidenceLink(
        supporting_evidence_link_id="sel_test",
        source_reference_id="src_test",
        document_id="doc_test",
        evidence_span_id="span_test",
        extracted_artifact_id="claim_test",
        role=EvidenceLinkRole.SUPPORT,
        quote="Apex reported first-quarter revenue growth.",
        note="Direct operating result statement.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _confidence() -> ConfidenceAssessment:
    return ConfidenceAssessment(
        confidence=0.55,
        uncertainty=0.45,
        method="unit_test",
        rationale="Unit test confidence payload.",
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_reference_ids=["src_test"],
        processing_time=FIXED_NOW,
    )
