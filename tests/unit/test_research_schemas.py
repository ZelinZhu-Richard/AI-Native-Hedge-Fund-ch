from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    ConfidenceAssessment,
    CounterHypothesis,
    CritiqueKind,
    EvidenceAssessment,
    EvidenceGrade,
    EvidenceLinkRole,
    Hypothesis,
    HypothesisStatus,
    ProvenanceRecord,
    ResearchBrief,
    ResearchReviewStatus,
    ResearchStance,
    ResearchValidationStatus,
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
            validation_status=ResearchValidationStatus.UNVALIDATED,
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
            validation_status=ResearchValidationStatus.UNVALIDATED,
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
            validation_status=ResearchValidationStatus.UNVALIDATED,
            next_validation_steps=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_research_artifacts_require_validation_status() -> None:
    supporting_link = _supporting_link()

    with pytest.raises(ValidationError):
        Hypothesis.model_validate(
            {
                "hypothesis_id": "hyp_valid_missing_validation",
                "company_id": "co_test",
                "title": "Validation Missing",
                "thesis": "A valid-looking hypothesis without validation status should fail.",
                "stance": ResearchStance.POSITIVE,
                "status": HypothesisStatus.UNDER_REVIEW,
                "review_status": ResearchReviewStatus.PENDING_HUMAN_REVIEW,
                "time_horizon": "next_2_4_quarters",
                "invalidation_conditions": ["Guidance is lowered."],
                "supporting_evidence_links": [supporting_link],
                "assumptions": ["Demand remains stable."],
                "uncertainties": ["Evidence is management-sourced."],
                "validation_steps": ["Check the next earnings update."],
                "confidence": _confidence(),
                "provenance": _provenance(),
                "created_at": FIXED_NOW,
                "updated_at": FIXED_NOW,
            }
        )

    with pytest.raises(ValidationError):
        EvidenceAssessment.model_validate(
            {
                "evidence_assessment_id": "eass_missing_validation",
                "company_id": "co_test",
                "hypothesis_id": "hyp_test",
                "grade": EvidenceGrade.MODERATE,
                "supporting_evidence_link_ids": [supporting_link.supporting_evidence_link_id],
                "support_summary": "Support exists but validation status is omitted.",
                "key_gaps": ["Independent confirmation is still missing."],
                "contradiction_notes": [],
                "review_status": ResearchReviewStatus.PENDING_HUMAN_REVIEW,
                "confidence": _confidence(),
                "provenance": _provenance(),
                "created_at": FIXED_NOW,
                "updated_at": FIXED_NOW,
            }
        )

    with pytest.raises(ValidationError):
        CounterHypothesis.model_validate(
            {
                "counter_hypothesis_id": "chyp_missing_validation",
                "hypothesis_id": "hyp_test",
                "title": "Validation Missing",
                "thesis": "A critique without validation status should fail.",
                "critique_kinds": [CritiqueKind.MISSING_EVIDENCE],
                "supporting_evidence_links": [supporting_link],
                "challenged_assumptions": [
                    "Management commentary may not reflect durable demand."
                ],
                "missing_evidence": ["Independent confirmation is still missing."],
                "causal_gaps": ["Current commentary does not prove durable monetization."],
                "unresolved_questions": ["Will pilots convert into broad adoption?"],
                "review_status": ResearchReviewStatus.PENDING_HUMAN_REVIEW,
                "confidence": _confidence(),
                "provenance": _provenance(),
                "created_at": FIXED_NOW,
                "updated_at": FIXED_NOW,
            }
        )

    with pytest.raises(ValidationError):
        ResearchBrief.model_validate(
            {
                "research_brief_id": "rbrief_missing_validation",
                "company_id": "co_test",
                "title": "Validation Missing",
                "context_summary": "Context exists.",
                "core_hypothesis": "Core hypothesis exists.",
                "counter_hypothesis_summary": "Counter summary exists.",
                "hypothesis_id": "hyp_test",
                "counter_hypothesis_id": "chyp_test",
                "evidence_assessment_id": "eass_test",
                "supporting_evidence_links": [supporting_link],
                "key_counterarguments": ["Adoption remains unproven."],
                "confidence": _confidence(),
                "uncertainty_summary": "Evidence is incomplete.",
                "review_status": ResearchReviewStatus.PENDING_HUMAN_REVIEW,
                "next_validation_steps": ["Check the next earnings update."],
                "provenance": _provenance(),
                "created_at": FIXED_NOW,
                "updated_at": FIXED_NOW,
            }
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
