from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libraries.schemas import (
    AblationView,
    ConfidenceAssessment,
    DerivedArtifactValidationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    EvidenceLinkRole,
    FeatureFamily,
    ProvenanceRecord,
    ResearchReviewStatus,
    ResearchStance,
    ResearchValidationStatus,
    Signal,
    SignalLineage,
    SignalScore,
    SignalStatus,
    SupportingEvidenceLink,
)
from libraries.time import FrozenClock
from services.signal_arbitration.rules import (
    build_arbitration_decision,
    build_signal_calibrations,
    detect_signal_conflicts,
)

FIXED_NOW = datetime(2026, 3, 22, 10, 0, tzinfo=UTC)


def test_single_signal_arbitration_selects_the_only_candidate() -> None:
    signal = _signal(signal_id="sig_primary", stance=ResearchStance.POSITIVE, score=0.6)
    assessment = _assessment(hypothesis_id=signal.hypothesis_id, grade=EvidenceGrade.MODERATE)
    candidates, excluded_signals = build_signal_calibrations(
        signals=[signal],
        evidence_assessments_by_hypothesis_id={signal.hypothesis_id: assessment},
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    conflicts = detect_signal_conflicts(
        candidates=candidates,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    decision, bundle = build_arbitration_decision(
        company_id=signal.company_id,
        component_signals=[signal],
        candidates=candidates,
        excluded_signals=excluded_signals,
        conflicts=conflicts,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert conflicts == []
    assert excluded_signals == []
    assert decision.selected_primary_signal_id == signal.signal_id
    assert bundle.component_signal_ids == [signal.signal_id]


def test_directional_disagreement_blocks_primary_selection_when_both_signals_are_supported() -> None:
    left = _signal(signal_id="sig_bull", stance=ResearchStance.POSITIVE, score=0.8)
    right = _signal(signal_id="sig_bear", stance=ResearchStance.NEGATIVE, score=-0.7)
    assessments = {
        left.hypothesis_id: _assessment(
            hypothesis_id=left.hypothesis_id,
            grade=EvidenceGrade.MODERATE,
        ),
        right.hypothesis_id: _assessment(
            hypothesis_id=right.hypothesis_id,
            grade=EvidenceGrade.STRONG,
        ),
    }
    candidates, excluded_signals = build_signal_calibrations(
        signals=[left, right],
        evidence_assessments_by_hypothesis_id=assessments,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    conflicts = detect_signal_conflicts(
        candidates=candidates,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    decision, _bundle = build_arbitration_decision(
        company_id=left.company_id,
        component_signals=[left, right],
        candidates=candidates,
        excluded_signals=excluded_signals,
        conflicts=conflicts,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert any(conflict.blocking for conflict in conflicts)
    assert any(
        conflict.conflict_kind.value == "directional_disagreement" for conflict in conflicts
    )
    assert decision.selected_primary_signal_id is None


def test_high_score_with_weak_support_creates_support_mismatch_conflict() -> None:
    signal = _signal(signal_id="sig_weak", stance=ResearchStance.POSITIVE, score=0.9)
    candidates, _excluded_signals = build_signal_calibrations(
        signals=[signal],
        evidence_assessments_by_hypothesis_id={
            signal.hypothesis_id: _assessment(
                hypothesis_id=signal.hypothesis_id,
                grade=EvidenceGrade.WEAK,
            )
        },
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    conflicts = detect_signal_conflicts(
        candidates=candidates,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert any(conflict.conflict_kind.value == "score_support_mismatch" for conflict in conflicts)


def test_stale_signal_loses_rank_to_fresher_signal() -> None:
    stale = _signal(
        signal_id="sig_stale",
        stance=ResearchStance.POSITIVE,
        score=0.9,
        effective_at=FIXED_NOW - timedelta(days=7),
    )
    fresh = _signal(
        signal_id="sig_fresh",
        stance=ResearchStance.POSITIVE,
        score=0.6,
        effective_at=FIXED_NOW - timedelta(hours=8),
    )
    assessments = {
        stale.hypothesis_id: _assessment(
            hypothesis_id=stale.hypothesis_id,
            grade=EvidenceGrade.MODERATE,
        ),
        fresh.hypothesis_id: _assessment(
            hypothesis_id=fresh.hypothesis_id,
            grade=EvidenceGrade.MODERATE,
        ),
    }
    candidates, excluded_signals = build_signal_calibrations(
        signals=[stale, fresh],
        evidence_assessments_by_hypothesis_id=assessments,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    conflicts = detect_signal_conflicts(
        candidates=candidates,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    decision, _bundle = build_arbitration_decision(
        company_id=stale.company_id,
        component_signals=[stale, fresh],
        candidates=candidates,
        excluded_signals=excluded_signals,
        conflicts=conflicts,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert any(conflict.conflict_kind.value == "freshness_mismatch" for conflict in conflicts)
    assert decision.selected_primary_signal_id == fresh.signal_id


def test_duplicate_support_suppresses_lower_ranked_signal() -> None:
    stronger = _signal(signal_id="sig_a", stance=ResearchStance.POSITIVE, score=0.8)
    weaker = _signal(signal_id="sig_b", stance=ResearchStance.POSITIVE, score=0.4)
    weaker = weaker.model_copy(
        update={
            "lineage": weaker.lineage.model_copy(
                update={
                    "supporting_evidence_link_ids": stronger.lineage.supporting_evidence_link_ids
                }
            )
        }
    )
    assessments = {
        stronger.hypothesis_id: _assessment(
            hypothesis_id=stronger.hypothesis_id,
            grade=EvidenceGrade.MODERATE,
        ),
        weaker.hypothesis_id: _assessment(
            hypothesis_id=weaker.hypothesis_id,
            grade=EvidenceGrade.MODERATE,
        ),
    }
    candidates, excluded_signals = build_signal_calibrations(
        signals=[stronger, weaker],
        evidence_assessments_by_hypothesis_id=assessments,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    conflicts = detect_signal_conflicts(
        candidates=candidates,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    decision, _bundle = build_arbitration_decision(
        company_id=stronger.company_id,
        component_signals=[stronger, weaker],
        candidates=candidates,
        excluded_signals=excluded_signals,
        conflicts=conflicts,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert any(
        conflict.conflict_kind.value == "duplicate_support_overlap" for conflict in conflicts
    )
    assert weaker.signal_id in decision.suppressed_signal_ids
    assert any(
        explanation.signal_id == weaker.signal_id
        and explanation.why_not_selected is not None
        for explanation in decision.ranking_explanations
    )
    assert decision.selected_primary_signal_id == stronger.signal_id


def test_missing_confidence_defaults_uncertainty_to_one() -> None:
    signal = _signal(signal_id="sig_missing_conf", stance=ResearchStance.POSITIVE, score=0.5)
    signal = signal.model_copy(update={"confidence": None})
    candidates, excluded_signals = build_signal_calibrations(
        signals=[signal],
        evidence_assessments_by_hypothesis_id={},
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert excluded_signals == []
    assert candidates[0].calibration.uncertainty_estimate.uncertainty_score == 1.0
    assert (
        candidates[0].calibration.uncertainty_estimate.base_uncertainty_source
        == "missing_confidence_fallback"
    )


def test_future_effective_signal_is_excluded_before_calibration() -> None:
    future_signal = _signal(
        signal_id="sig_future",
        stance=ResearchStance.POSITIVE,
        score=0.6,
        effective_at=FIXED_NOW + timedelta(hours=3),
    )

    candidates, excluded_signals = build_signal_calibrations(
        signals=[future_signal],
        evidence_assessments_by_hypothesis_id={},
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    conflicts = detect_signal_conflicts(
        candidates=candidates,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )
    decision, bundle = build_arbitration_decision(
        company_id=future_signal.company_id,
        component_signals=[future_signal],
        candidates=candidates,
        excluded_signals=excluded_signals,
        conflicts=conflicts,
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert candidates == []
    assert decision.selected_primary_signal_id is None
    assert decision.candidate_signal_ids == []
    assert decision.excluded_signals[0].signal_id == future_signal.signal_id
    assert decision.excluded_signals[0].reason.value == "future_effective_at_as_of_time"
    assert bundle.signal_calibration_ids == []


def test_rejected_expired_and_invalidated_signals_are_recorded_as_excluded() -> None:
    rejected = _signal(
        signal_id="sig_rejected",
        stance=ResearchStance.POSITIVE,
        score=0.6,
    ).model_copy(update={"status": SignalStatus.REJECTED})
    expired = _signal(
        signal_id="sig_expired",
        stance=ResearchStance.POSITIVE,
        score=0.5,
    ).model_copy(update={"status": SignalStatus.EXPIRED})
    invalidated = _signal(
        signal_id="sig_invalidated",
        stance=ResearchStance.POSITIVE,
        score=0.4,
    ).model_copy(
        update={"validation_status": DerivedArtifactValidationStatus.INVALIDATED}
    )

    candidates, excluded_signals = build_signal_calibrations(
        signals=[rejected, expired, invalidated],
        evidence_assessments_by_hypothesis_id={},
        as_of_time=FIXED_NOW,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="sarbit_test",
    )

    assert candidates == []
    assert {row.reason.value for row in excluded_signals} == {
        "rejected",
        "expired",
        "invalidated",
    }


def _signal(
    *,
    signal_id: str,
    stance: ResearchStance,
    score: float,
    effective_at: datetime = FIXED_NOW - timedelta(hours=2),
) -> Signal:
    return Signal(
        signal_id=signal_id,
        company_id="co_test",
        hypothesis_id=f"hyp_{signal_id}",
        signal_family="text_only_candidate_signal",
        stance=stance,
        ablation_view=AblationView.TEXT_ONLY,
        thesis_summary="Unit test signal.",
        feature_ids=[f"feat_{signal_id}"],
        component_scores=[
            SignalScore(
                signal_score_id=f"sscore_{signal_id}",
                metric_name="support_grade_component",
                value=score,
                scale_min=-1.0,
                scale_max=1.0,
                validation_status=DerivedArtifactValidationStatus.VALIDATED,
                source_feature_ids=[f"feat_{signal_id}"],
                assumptions=["Unit test score."],
                provenance=_provenance(),
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        ],
        primary_score=score,
        effective_at=effective_at,
        status=SignalStatus.CANDIDATE,
        validation_status=DerivedArtifactValidationStatus.VALIDATED,
        lineage=SignalLineage(
            signal_lineage_id=f"slin_{signal_id}",
            feature_ids=[f"feat_{signal_id}"],
            feature_definition_ids=[f"fdef_{signal_id}"],
            feature_value_ids=[f"fval_{signal_id}"],
            research_artifact_ids=[f"eass_{signal_id}", f"brief_{signal_id}"],
            supporting_evidence_link_ids=[f"link_{signal_id}"],
            input_families=[FeatureFamily.TEXT_DERIVED],
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        assumptions=["Unit test assumption."],
        uncertainties=["Unit test uncertainty."],
        confidence=ConfidenceAssessment(
            confidence=0.55,
            uncertainty=0.45,
            method="unit_test",
            rationale="Synthetic payload.",
        ),
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _assessment(*, hypothesis_id: str, grade: EvidenceGrade) -> EvidenceAssessment:
    link = SupportingEvidenceLink(
        supporting_evidence_link_id=f"link_{hypothesis_id}",
        source_reference_id="src_test",
        document_id="doc_test",
        evidence_span_id="espan_test",
        role=EvidenceLinkRole.SUPPORT,
        quote="Unit test support.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    return EvidenceAssessment(
        evidence_assessment_id=f"eass_{hypothesis_id}",
        company_id="co_test",
        hypothesis_id=hypothesis_id,
        grade=grade,
        supporting_evidence_link_ids=[link.supporting_evidence_link_id],
        support_summary="Unit test support summary.",
        key_gaps=[],
        contradiction_notes=[],
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        confidence=ConfidenceAssessment(confidence=0.55, uncertainty=0.45),
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(source_reference_ids=["src_test"], processing_time=FIXED_NOW)
