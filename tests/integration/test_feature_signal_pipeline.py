from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import DerivedArtifactValidationStatus, SignalStatus
from libraries.time import FrozenClock
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import run_feature_signal_pipeline

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"


def test_feature_signal_pipeline_persists_candidate_outputs(tmp_path: Path) -> None:
    fixed_now = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)
    artifact_root = tmp_path / "artifacts"

    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=artifact_root / "ingestion",
        clock=FrozenClock(fixed_now),
    )
    run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=FrozenClock(fixed_now),
    )
    run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(fixed_now),
    )
    response = run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(fixed_now),
    )

    assert response.feature_mapping.features
    assert response.signal_generation.signals
    assert response.signal_arbitration.signal_bundle is not None
    assert response.signal_arbitration.arbitration_decision is not None
    feature = response.feature_mapping.features[0]
    signal = response.signal_generation.signals[0]
    signal_bundle = response.signal_arbitration.signal_bundle
    arbitration_decision = response.signal_arbitration.arbitration_decision

    feature_path = artifact_root / "signal_generation" / "features" / f"{feature.feature_id}.json"
    signal_path = artifact_root / "signal_generation" / "signals" / f"{signal.signal_id}.json"
    signal_bundle_path = (
        artifact_root
        / "signal_arbitration"
        / "signal_bundles"
        / f"{signal_bundle.signal_bundle_id}.json"
    )
    arbitration_decision_path = (
        artifact_root
        / "signal_arbitration"
        / "arbitration_decisions"
        / f"{arbitration_decision.arbitration_decision_id}.json"
    )
    assert feature_path.exists()
    assert signal_path.exists()
    assert signal_bundle_path.exists()
    assert arbitration_decision_path.exists()

    feature_payload = json.loads(feature_path.read_text(encoding="utf-8"))
    signal_payload = json.loads(signal_path.read_text(encoding="utf-8"))
    assert (
        feature_payload["validation_status"]
        == DerivedArtifactValidationStatus.UNVALIDATED.value
    )
    assert signal_payload["status"] == SignalStatus.CANDIDATE.value
    assert (
        signal_payload["validation_status"]
        == DerivedArtifactValidationStatus.UNVALIDATED.value
    )

    research_hypothesis_ids = {
        path.stem for path in (artifact_root / "research" / "hypotheses").glob("*.json")
    }
    assert feature.lineage.hypothesis_id in research_hypothesis_ids
    assert set(feature.lineage.supporting_evidence_link_ids)
    assert set(signal.lineage.feature_ids) == {
        mapped_feature.feature_id for mapped_feature in response.feature_mapping.features
    }
    assert set(signal.lineage.supporting_evidence_link_ids) == {
        supporting_evidence_link_id
        for mapped_feature in response.feature_mapping.features
        for supporting_evidence_link_id in mapped_feature.lineage.supporting_evidence_link_ids
    }
    assert signal_bundle.component_signal_ids == [signal.signal_id]
    assert arbitration_decision.selected_primary_signal_id == signal.signal_id
