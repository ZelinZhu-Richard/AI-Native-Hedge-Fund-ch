from __future__ import annotations

from datetime import UTC, datetime

import pytest

from libraries.schemas import (
    ActionRecommendationSummary,
    EscalationStatus,
    EvidenceLinkRole,
    ResearchBrief,
    ResearchReviewStatus,
    ResearchValidationStatus,
    ReviewAssignment,
    ReviewContext,
    ReviewDecision,
    ReviewNote,
    ReviewOutcome,
    ReviewQueueItem,
    ReviewQueueStatus,
    ReviewTargetType,
    SupportingEvidenceLink,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)


def test_review_queue_item_requires_target_linkage_and_recommendation() -> None:
    queue_item = ReviewQueueItem(
        review_queue_item_id="rqueue_test",
        target_type=ReviewTargetType.SIGNAL,
        target_id="sig_test",
        queue_status=ReviewQueueStatus.PENDING_REVIEW,
        current_target_status="candidate",
        title="APEX text signal",
        summary="Candidate signal requires operator review.",
        submitted_at=FIXED_NOW,
        escalation_status=EscalationStatus.NONE,
        action_recommendation=ActionRecommendationSummary(summary="Manual review required."),
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert queue_item.target_type is ReviewTargetType.SIGNAL
    assert queue_item.action_recommendation.summary == "Manual review required."


def test_review_note_requires_non_empty_body() -> None:
    with pytest.raises(ValueError, match="body must be non-empty"):
        ReviewNote(
            review_note_id="rnote_test",
            target_type=ReviewTargetType.RESEARCH_BRIEF,
            target_id="brief_test",
            author_id="analyst_1",
            created_at=FIXED_NOW,
            body="",
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            updated_at=FIXED_NOW,
        )


def test_review_assignment_requires_queue_linkage() -> None:
    assignment = ReviewAssignment(
        review_assignment_id="rassign_test",
        queue_item_id="rqueue_test",
        assigned_by="lead_reviewer",
        assignee_id="analyst_1",
        assigned_at=FIXED_NOW,
        active=True,
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert assignment.active is True


def test_review_decision_is_generic_across_target_types() -> None:
    decision = ReviewDecision(
        review_decision_id="review_test",
        target_type=ReviewTargetType.SIGNAL,
        target_id="sig_test",
        reviewer_id="pm_1",
        outcome=ReviewOutcome.NEEDS_REVISION,
        decided_at=FIXED_NOW,
        rationale="Lineage is incomplete.",
        blocking_issues=[],
        conditions=["restore missing uncertainty disclosure"],
        review_notes=["needs more detail"],
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert decision.target_type is ReviewTargetType.SIGNAL
    assert decision.outcome is ReviewOutcome.NEEDS_REVISION


def test_review_context_requires_one_reviewable_payload() -> None:
    queue_item = ReviewQueueItem(
        review_queue_item_id="rqueue_test",
        target_type=ReviewTargetType.RESEARCH_BRIEF,
        target_id="brief_test",
        queue_status=ReviewQueueStatus.PENDING_REVIEW,
        current_target_status="pending_human_review",
        title="APEX research brief",
        summary="Review the current thesis.",
        submitted_at=FIXED_NOW,
        escalation_status=EscalationStatus.NONE,
        action_recommendation=ActionRecommendationSummary(summary="Manual review required."),
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    research_brief = ResearchBrief(
        research_brief_id="brief_test",
        company_id="co_apex",
        title="APEX research brief",
        context_summary="Current quarter review context.",
        core_hypothesis="Execution remains on plan.",
        counter_hypothesis_summary="Demand could soften.",
        hypothesis_id="hyp_test",
        counter_hypothesis_id="counter_test",
        evidence_assessment_id="assess_test",
        supporting_evidence_links=[
            SupportingEvidenceLink(
                supporting_evidence_link_id="sel_test",
                source_reference_id="src_test",
                document_id="doc_test",
                evidence_span_id="span_test",
                extracted_artifact_id=None,
                role=EvidenceLinkRole.SUPPORT,
                quote="Management maintained guidance.",
                provenance=ProvenanceRecord(processing_time=FIXED_NOW),
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        ],
        key_counterarguments=["Macro demand is still uncertain."],
        confidence=None,
        uncertainty_summary="Demand remains uncertain.",
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        next_validation_steps=["Re-check next earnings call guidance language."],
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    context = ReviewContext(
        queue_item=queue_item,
        research_brief=research_brief,
        action_recommendation=queue_item.action_recommendation,
    )

    assert context.research_brief is not None
    assert context.queue_item.target_id == "brief_test"

    with pytest.raises(ValueError, match="requires at least one reviewable target payload"):
        ReviewContext(
            queue_item=queue_item,
            action_recommendation=queue_item.action_recommendation,
        )
