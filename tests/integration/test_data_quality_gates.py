from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libraries.core import load_local_models
from libraries.schemas import RefusalReason, RunSummary, ValidationGate, WorkflowStatus
from libraries.time import FrozenClock
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.signal_generation import run_feature_signal_pipeline
from services.data_quality import DataQualityRefusalError

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_broken_signal_is_blocked_before_portfolio_proposal_persistence(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_research_and_signal_artifacts(artifact_root=artifact_root)
    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    payload = json.loads(signal_path.read_text(encoding="utf-8"))
    payload["feature_ids"] = ["feat_missing_for_quality_gate"]
    signal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(DataQualityRefusalError) as exc_info:
        run_portfolio_review_pipeline(
            signal_root=artifact_root / "signal_generation",
            research_root=artifact_root / "research",
            ingestion_root=artifact_root / "ingestion",
            output_root=artifact_root / "portfolio",
            clock=FrozenClock(FIXED_NOW),
        )

    gate = exc_info.value.result.validation_gate
    assert gate.gate_name == "portfolio_proposal"
    assert gate.refusal_reason is RefusalReason.BROKEN_SIGNAL_LINEAGE
    assert not any((artifact_root / "portfolio" / "portfolio_proposals").glob("*.json"))

    persisted_gates = load_local_models(
        artifact_root / "data_quality" / "validation_gates",
        ValidationGate,
        required=True,
        label="Data-quality validation gates",
    )
    assert any(
        persisted_gate.validation_gate_id == gate.validation_gate_id
        and persisted_gate.refusal_reason == gate.refusal_reason
        for persisted_gate in persisted_gates
    )

    run_summaries = load_local_models(
        artifact_root / "monitoring" / "run_summaries",
        RunSummary,
        required=True,
        label="Monitoring run summaries",
    )
    portfolio_summary = next(
        summary
        for summary in run_summaries
        if summary.workflow_name == "portfolio_review_pipeline"
    )
    assert portfolio_summary.status is WorkflowStatus.FAILED
    assert any(
        note == f"validation_gate_id={gate.validation_gate_id}"
        for note in portfolio_summary.notes
    )


def _build_research_and_signal_artifacts(*, artifact_root: Path) -> None:
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
    run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(FIXED_NOW),
    )
