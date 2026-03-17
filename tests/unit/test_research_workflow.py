from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import (
    ConfidenceAssessment,
    EvidenceGrade,
    EvidenceSpan,
    ProvenanceRecord,
    ResearchReviewStatus,
    ResearchValidationStatus,
    ToneMarker,
    ToneMarkerType,
)
from libraries.time import FrozenClock
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from services.research_orchestrator.grading import build_evidence_assessment
from services.research_orchestrator.hypothesis import generate_hypothesis
from services.research_orchestrator.loaders import LoadedResearchArtifacts as WorkflowInputs

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
FIXED_NOW = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)


def test_apex_workflow_produces_reviewable_hypothesis_and_critique(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=artifact_root / "ingestion",
        clock=FrozenClock(FIXED_NOW),
    )
    run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=FrozenClock(FIXED_NOW),
    )

    response = run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.status == "completed"
    assert response.hypothesis is not None
    assert response.counter_hypothesis is not None
    assert response.research_brief is not None
    assert response.memo is not None
    assert len(response.hypothesis.supporting_evidence_links) >= 3
    assert len({link.document_id for link in response.hypothesis.supporting_evidence_links}) >= 2
    assert response.evidence_assessment.grade in {EvidenceGrade.STRONG, EvidenceGrade.MODERATE}
    assert response.hypothesis.review_status == ResearchReviewStatus.PENDING_HUMAN_REVIEW
    assert response.hypothesis.validation_status == ResearchValidationStatus.UNVALIDATED
    assert response.evidence_assessment.review_status == ResearchReviewStatus.PENDING_HUMAN_REVIEW
    assert response.evidence_assessment.validation_status == ResearchValidationStatus.PENDING_VALIDATION
    assert response.counter_hypothesis.review_status == ResearchReviewStatus.PENDING_HUMAN_REVIEW
    assert response.counter_hypothesis.validation_status == ResearchValidationStatus.UNVALIDATED
    assert response.research_brief.review_status == response.hypothesis.review_status
    assert response.research_brief.validation_status == response.hypothesis.validation_status
    assert response.counter_hypothesis.challenged_assumptions
    assert response.counter_hypothesis.missing_evidence
    assert response.research_brief.key_counterarguments
    assert response.research_brief.core_hypothesis == response.hypothesis.thesis
    assert response.research_brief.core_hypothesis in response.memo.executive_summary
    assert "Review status:" in response.memo.executive_summary
    assert "Validation status:" in response.memo.executive_summary


def test_insufficient_evidence_returns_no_hypothesis() -> None:
    inputs = WorkflowInputs(
        company_id="co_test",
        evidence_spans=[_evidence_span()],
        tone_markers=[_tone_marker()],
    )

    result = generate_hypothesis(
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="rflow_test",
        agent_run_id="arun_test",
    )
    assessment = build_evidence_assessment(
        company_id=inputs.company_id,
        hypothesis=result.hypothesis,
        supporting_evidence_links=result.supporting_evidence_links,
        generation_notes=result.notes,
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="rflow_test",
        agent_run_id="arun_grade",
    )

    assert result.hypothesis is None
    assert result.notes
    assert assessment.grade == EvidenceGrade.INSUFFICIENT
    assert assessment.validation_status == ResearchValidationStatus.UNVALIDATED


def _evidence_span() -> EvidenceSpan:
    return EvidenceSpan(
        evidence_span_id="span_test",
        source_reference_id="src_test",
        document_id="doc_test",
        segment_id="seg_test",
        text="Management said execution remained on plan.",
        start_char=0,
        end_char=42,
        page_number=None,
        speaker="CEO",
        captured_at=FIXED_NOW,
        confidence=ConfidenceAssessment(
            confidence=0.7,
            uncertainty=0.3,
            method="unit_test",
            rationale="Synthetic span.",
        ),
        provenance=ProvenanceRecord(source_reference_ids=["src_test"], processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _tone_marker() -> ToneMarker:
    return ToneMarker(
        tone_marker_id="tone_test",
        document_id="doc_test",
        source_reference_id="src_test",
        company_id="co_test",
        segment_id="seg_test",
        statement="Management said execution remained on plan.",
        evidence_span_ids=["span_test"],
        speaker="CEO",
        confidence=None,
        provenance=ProvenanceRecord(source_reference_ids=["src_test"], processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
        marker_type=ToneMarkerType.CONFIDENCE,
        cue_phrase="on plan",
    )
