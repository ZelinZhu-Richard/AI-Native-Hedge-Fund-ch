from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libraries.time import FrozenClock
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import run_feature_signal_pipeline
from services.portfolio import PortfolioConstructionService, RunPortfolioWorkflowRequest
from services.signal_arbitration import RunSignalArbitrationRequest, SignalArbitrationService

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
FIXED_NOW = datetime(2026, 3, 22, 11, 0, tzinfo=UTC)


def test_signal_arbitration_blocks_portfolio_input_when_conflicting_primary_signals_exist(
    tmp_path: Path,
) -> None:
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

    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    payload = json.loads(signal_path.read_text(encoding="utf-8"))
    bearish_payload = {
        **payload,
        "signal_id": f"{payload['signal_id']}_bearish",
        "stance": "negative",
        "signal_family": "price_only_candidate_signal",
        "primary_score": -0.72,
    }
    bearish_payload["component_scores"][0]["signal_score_id"] = (
        f"{payload['component_scores'][0]['signal_score_id']}_bearish"
    )
    (artifact_root / "signal_generation" / "signals" / f"{bearish_payload['signal_id']}.json").write_text(
        json.dumps(bearish_payload, indent=2),
        encoding="utf-8",
    )

    arbitration_response = SignalArbitrationService(clock=FrozenClock(FIXED_NOW)).run_signal_arbitration(
        RunSignalArbitrationRequest(
            signal_root=artifact_root / "signal_generation",
            research_root=artifact_root / "research",
            output_root=artifact_root / "signal_arbitration",
            requested_by="integration_test",
        )
    )

    assert arbitration_response.signal_bundle is not None
    assert arbitration_response.arbitration_decision is not None
    assert arbitration_response.arbitration_decision.selected_primary_signal_id is None
    assert any(
        conflict.conflict_kind.value == "directional_disagreement"
        for conflict in arbitration_response.signal_conflicts
    )

    portfolio_response = PortfolioConstructionService(clock=FrozenClock(FIXED_NOW)).run_portfolio_workflow(
        RunPortfolioWorkflowRequest(
            signal_root=artifact_root / "signal_generation",
            signal_arbitration_root=artifact_root / "signal_arbitration",
            research_root=artifact_root / "research",
            ingestion_root=artifact_root / "ingestion",
            output_root=artifact_root / "portfolio",
            requested_by="integration_test",
        )
    )

    assert portfolio_response.position_ideas == []
    assert any(
        "withheld a primary signal selection" in note for note in portfolio_response.notes
    )
