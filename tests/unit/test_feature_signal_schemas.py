from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    AblationView,
    ConfidenceAssessment,
    DerivedArtifactValidationStatus,
    Feature,
    FeatureDefinition,
    FeatureFamily,
    FeatureStatus,
    FeatureValue,
    FeatureValueType,
    ProvenanceRecord,
    ResearchStance,
    Signal,
    SignalScore,
    SignalStatus,
)

FIXED_NOW = datetime(2026, 3, 17, 10, 0, tzinfo=UTC)


def test_feature_requires_lineage() -> None:
    with pytest.raises(ValidationError):
        Feature.model_validate(
            {
                "feature_id": "feat_test",
                "entity_id": "co_test",
                "company_id": "co_test",
                "feature_definition": _feature_definition(),
                "feature_value": _feature_value(),
                "status": FeatureStatus.PROVISIONAL,
                "validation_status": DerivedArtifactValidationStatus.UNVALIDATED,
                "provenance": _provenance(),
                "created_at": FIXED_NOW,
                "updated_at": FIXED_NOW,
            }
        )


def test_signal_requires_lineage_and_validation_status() -> None:
    with pytest.raises(ValidationError):
        Signal.model_validate(
            {
                "signal_id": "sig_test",
                "company_id": "co_test",
                "hypothesis_id": "hyp_test",
                "signal_family": "text_only_candidate_signal",
                "stance": ResearchStance.POSITIVE,
                "ablation_view": AblationView.TEXT_ONLY,
                "thesis_summary": "Test signal.",
                "feature_ids": ["feat_test"],
                "component_scores": [_signal_score()],
                "primary_score": 0.45,
                "effective_at": FIXED_NOW,
                "status": SignalStatus.CANDIDATE,
                "assumptions": ["Unit test signal."],
                "uncertainties": ["Candidate-only."],
                "provenance": _provenance(),
                "created_at": FIXED_NOW,
                "updated_at": FIXED_NOW,
            }
        )


def _feature_definition() -> FeatureDefinition:
    return FeatureDefinition(
        feature_definition_id="fdef_test",
        name="support_grade_score",
        family=FeatureFamily.TEXT_DERIVED,
        value_type=FeatureValueType.NUMERIC,
        description="Map the evidence grade into a numeric score.",
        ablation_views=[AblationView.TEXT_ONLY, AblationView.COMBINED],
        status=FeatureStatus.PROVISIONAL,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _feature_value() -> FeatureValue:
    return FeatureValue(
        feature_value_id="fval_test",
        feature_definition_id="fdef_test",
        as_of_date=date(2026, 3, 17),
        available_at=FIXED_NOW,
        numeric_value=0.66,
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


def _signal_score() -> SignalScore:
    return SignalScore(
        signal_score_id="sscore_test",
        metric_name="support_grade_component",
        value=0.66,
        scale_min=0.0,
        scale_max=1.0,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        source_feature_ids=["feat_test"],
        assumptions=["Unit test score."],
        confidence=ConfidenceAssessment(
            confidence=0.50,
            uncertainty=0.50,
            method="unit_test",
            rationale="Synthetic payload.",
        ),
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_reference_ids=["src_test"],
        processing_time=FIXED_NOW,
    )
