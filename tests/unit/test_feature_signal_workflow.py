from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from libraries.config import get_settings
from libraries.schemas import (
    AblationView,
    DerivedArtifactValidationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    FeatureStatus,
    ProvenanceRecord,
    ResearchReviewStatus,
    ResearchValidationStatus,
    SignalStatus,
)
from libraries.time import FrozenClock
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import FeatureSignalPipelineResponse, run_feature_signal_pipeline
from services.feature_store import FeatureQueryRequest, FeatureStoreService
from services.feature_store.loaders import LoadedFeatureMappingInputs
from services.feature_store.mapping import build_feature_candidates
from services.signal_generation import (
    RunSignalGenerationWorkflowRequest,
    SignalGenerationService,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_feature_mapping_produces_initial_text_feature_set(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_research_artifacts(artifact_root=artifact_root)

    response = run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(FIXED_NOW),
    )

    feature_names = {
        feature.feature_definition.name for feature in response.feature_mapping.features
    }
    assert feature_names == {
        "support_grade_score",
        "support_document_count",
        "guidance_change_score",
        "risk_factor_count",
        "tone_balance_score",
        "counterargument_pressure_score",
    }
    assert all(feature.status == FeatureStatus.PROVISIONAL for feature in response.feature_mapping.features)
    assert all(
        feature.validation_status == DerivedArtifactValidationStatus.UNVALIDATED
        for feature in response.feature_mapping.features
    )
    assert all(feature.lineage.supporting_evidence_link_ids for feature in response.feature_mapping.features)
    assert all(
        feature.feature_value.availability_window is not None
        for feature in response.feature_mapping.features
    )
    assert any("not replay-safe" in note for note in response.feature_mapping.notes)
    assert any("not replay-safe" in note for note in response.signal_generation.notes)


def test_signal_generation_produces_candidate_signal_and_point_in_time_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        response = _build_feature_signal_artifacts(artifact_root=artifact_root)

        assert len(response.signal_generation.signals) == 1
        signal = response.signal_generation.signals[0]
        assert signal.status == SignalStatus.CANDIDATE
        assert signal.validation_status == DerivedArtifactValidationStatus.UNVALIDATED
        assert signal.component_scores
        assert signal.primary_score > 0.0
        assert signal.availability_window is not None
        assert set(signal.feature_ids) == {
            feature.feature_id for feature in response.feature_mapping.features
        }

        feature_store = FeatureStoreService(clock=FrozenClock(FIXED_NOW))
        query_response = feature_store.query_features(
            FeatureQueryRequest(
                entity_id=response.feature_mapping.company_id,
                as_of_time=signal.effective_at,
                feature_names=["support_grade_score", "guidance_change_score"],
            )
        )
        assert len(query_response.features) == 2
        assert {feature.feature_definition.name for feature in query_response.features} == {
            "support_grade_score",
            "guidance_change_score",
        }
    finally:
        get_settings.cache_clear()


def test_non_text_ablation_returns_no_candidate_signals(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_feature_signal_artifacts(artifact_root=artifact_root)

    service = SignalGenerationService(clock=FrozenClock(FIXED_NOW))
    response = service.run_signal_generation_workflow(
        RunSignalGenerationWorkflowRequest(
            feature_root=artifact_root / "signal_generation",
            research_root=artifact_root / "research",
            output_root=artifact_root / "signal_generation",
            ablation_view=AblationView.PRICE_ONLY,
            requested_by="unit_test",
        )
    )

    assert response.signals == []
    assert response.signal_scores == []
    assert response.notes


def test_insufficient_evidence_returns_no_features_or_signals() -> None:
    inputs = LoadedFeatureMappingInputs(
        company_id="co_test",
        evidence_assessment=EvidenceAssessment(
            evidence_assessment_id="eass_test",
            company_id="co_test",
            hypothesis_id=None,
            grade=EvidenceGrade.INSUFFICIENT,
            supporting_evidence_link_ids=[],
            support_summary="Support is insufficient.",
            key_gaps=["Need direct evidence."],
            contradiction_notes=[],
            review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
            validation_status=ResearchValidationStatus.UNVALIDATED,
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
    )

    result = build_feature_candidates(
        inputs=inputs,
        ablation_view=AblationView.TEXT_ONLY,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="fmap_test",
    )

    assert result.feature_definitions == []
    assert result.feature_values == []
    assert result.features == []
    assert result.notes


def _build_feature_signal_artifacts(*, artifact_root: Path) -> FeatureSignalPipelineResponse:
    _build_research_artifacts(artifact_root=artifact_root)
    return run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(FIXED_NOW),
    )


def _build_research_artifacts(*, artifact_root: Path) -> None:
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
    run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(FIXED_NOW),
    )
