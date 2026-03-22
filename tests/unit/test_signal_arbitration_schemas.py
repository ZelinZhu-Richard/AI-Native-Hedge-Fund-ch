from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    ArbitrationDecision,
    ArbitrationRule,
    DerivedArtifactValidationStatus,
    EvidenceGrade,
    ExcludedSignal,
    FreshnessState,
    ProvenanceRecord,
    RankingExplanation,
    SignalBundle,
    SignalCalibration,
    SignalConflict,
    SignalConflictKind,
    SignalExclusionReason,
    UncertaintyEstimate,
)

FIXED_NOW = datetime(2026, 3, 22, 10, 0, tzinfo=UTC)


def test_signal_calibration_requires_absolute_strength_to_match_normalized_score() -> None:
    with pytest.raises(ValidationError):
        SignalCalibration(
            signal_calibration_id="scal_test",
            signal_id="sig_test",
            company_id="co_test",
            raw_primary_score=0.7,
            normalized_score=0.7,
            absolute_strength=0.6,
            calibration_method="unit_test",
            uncertainty_estimate=_uncertainty_estimate(),
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_directional_conflict_requires_two_signal_ids() -> None:
    with pytest.raises(ValidationError):
        SignalConflict(
            signal_conflict_id="sconf_test",
            company_id="co_test",
            conflict_kind=SignalConflictKind.DIRECTIONAL_DISAGREEMENT,
            signal_ids=["sig_a"],
            blocking=True,
            message="Signals disagree directionally.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_score_support_mismatch_allows_one_signal_id() -> None:
    conflict = SignalConflict(
        signal_conflict_id="sconf_test",
        company_id="co_test",
        conflict_kind=SignalConflictKind.SCORE_SUPPORT_MISMATCH,
        signal_ids=["sig_a"],
        blocking=False,
        message="High score conflicts with weak support.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert conflict.signal_ids == ["sig_a"]


def test_ranking_explanation_requires_rule_trace() -> None:
    with pytest.raises(ValidationError):
        RankingExplanation(signal_id="sig_test", rank=1, rule_trace=[], warnings=[])


def test_signal_bundle_requires_component_and_calibration_linkage() -> None:
    with pytest.raises(ValidationError):
        SignalBundle(
            signal_bundle_id="sbundle_test",
            company_id="co_test",
            component_signal_ids=[],
            signal_calibration_ids=[],
            signal_conflict_ids=[],
            arbitration_decision_id="adec_test",
            bundle_summary="Unit test bundle.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_signal_bundle_allows_empty_calibrations_when_all_components_were_excluded() -> None:
    bundle = SignalBundle(
        signal_bundle_id="sbundle_test",
        company_id="co_test",
        component_signal_ids=["sig_a"],
        signal_calibration_ids=[],
        signal_conflict_ids=[],
        arbitration_decision_id="adec_test",
        bundle_summary="No eligible candidates remained after exclusions.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert bundle.signal_calibration_ids == []


def test_arbitration_decision_selected_signal_must_be_ranked() -> None:
    with pytest.raises(ValidationError):
        ArbitrationDecision(
            arbitration_decision_id="adec_test",
            company_id="co_test",
            candidate_signal_ids=["sig_a"],
            selected_primary_signal_id="sig_a",
            excluded_signals=[],
            prioritized_signal_ids=[],
            suppressed_signal_ids=[],
            applied_rules=[_rule()],
            conflict_ids=[],
            ranking_explanations=[],
            review_required=True,
            summary="Selected signal.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_arbitration_decision_rejects_excluded_candidate_overlap() -> None:
    with pytest.raises(ValidationError):
        ArbitrationDecision(
            arbitration_decision_id="adec_test",
            company_id="co_test",
            candidate_signal_ids=["sig_a"],
            selected_primary_signal_id=None,
            excluded_signals=[
                ExcludedSignal(
                    signal_id="sig_a",
                    reason=SignalExclusionReason.REJECTED,
                    message="Rejected before ranking.",
                )
            ],
            prioritized_signal_ids=["sig_a"],
            suppressed_signal_ids=[],
            applied_rules=[_rule()],
            conflict_ids=[],
            ranking_explanations=[
                RankingExplanation(
                    signal_id="sig_a",
                    rank=1,
                    rule_trace=["validation_status=validated"],
                    warnings=[],
                )
            ],
            review_required=True,
            summary="Excluded/candidate overlap.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_arbitration_decision_allows_explanations_for_suppressed_candidates() -> None:
    decision = ArbitrationDecision(
        arbitration_decision_id="adec_test",
        company_id="co_test",
        candidate_signal_ids=["sig_a", "sig_b"],
        selected_primary_signal_id="sig_a",
        excluded_signals=[],
        prioritized_signal_ids=["sig_a"],
        suppressed_signal_ids=["sig_b"],
        applied_rules=[_rule()],
        conflict_ids=[],
        ranking_explanations=[
            RankingExplanation(
                signal_id="sig_a",
                rank=1,
                rule_trace=["validation_status=validated"],
                warnings=[],
            ),
            RankingExplanation(
                signal_id="sig_b",
                rank=2,
                rule_trace=["validation_status=validated"],
                warnings=[],
                why_not_selected="Suppressed due to duplicate support with a higher-ranked signal.",
            ),
        ],
        review_required=True,
        summary="Selected sig_a after suppression.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert [row.signal_id for row in decision.ranking_explanations] == ["sig_a", "sig_b"]


def _uncertainty_estimate() -> UncertaintyEstimate:
    return UncertaintyEstimate(
        uncertainty_estimate_id="uest_test",
        signal_id="sig_test",
        uncertainty_score=0.4,
        base_uncertainty_source="signal_confidence",
        lineage_complete=True,
        validation_status=DerivedArtifactValidationStatus.VALIDATED,
        evidence_grade=EvidenceGrade.MODERATE,
        freshness_state=FreshnessState.FRESH,
        factors=["validation_status=validated"],
        method_name="unit_test",
        provenance=_provenance(),
    )


def _rule() -> ArbitrationRule:
    return ArbitrationRule(
        arbitration_rule_id="arule_test",
        rule_name="unit_test_rule",
        description="Unit test rule.",
        priority=1,
        blocking=False,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
