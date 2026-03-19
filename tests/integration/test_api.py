from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from libraries.config import get_settings
from libraries.schemas import AblationView, BacktestConfig, BenchmarkKind, ExecutionAssumption
from libraries.schemas.base import ProvenanceRecord
from libraries.time import FrozenClock
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_backtest_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.signal_generation import run_feature_signal_pipeline

client = TestClient(app)
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_api_health_and_version() -> None:
    health_response = client.get("/health")
    version_response = client.get("/version")

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert version_response.status_code == 200
    assert version_response.json()["version"] == "0.1.0"


def test_monitoring_api_endpoints_return_structured_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        _build_full_stack(artifact_root=artifact_root)

        health_details_response = client.get("/health/details")
        run_summaries_response = client.get("/monitoring/run-summaries/recent")
        failure_summaries_response = client.get("/monitoring/failures/recent")
        service_status_response = client.get("/monitoring/services")

        assert health_details_response.status_code == 200
        assert health_details_response.json()["health_checks"]
        assert service_status_response.status_code == 200
        assert service_status_response.json()["total"] >= 1
        assert any(
            item["service_name"] == "monitoring"
            for item in service_status_response.json()["items"]
        )
        assert run_summaries_response.status_code == 200
        assert run_summaries_response.json()["total"] >= 1
        assert failure_summaries_response.status_code == 200
        assert "run_summaries" in failure_summaries_response.json()
        assert "alert_records" in failure_summaries_response.json()
    finally:
        get_settings.cache_clear()


def test_capabilities_and_document_ingestion_placeholder() -> None:
    capabilities_response = client.get("/capabilities")
    ingest_response = client.post(
        "/documents/ingest",
        json={
            "source_reference_id": "src_test",
            "document_kind": "filing",
            "title": "Sample Filing",
            "raw_text": "payload",
            "requested_by": "integration_test",
        },
    )

    assert capabilities_response.status_code == 200
    assert len(capabilities_response.json()["services"]) >= 5
    assert "name" in capabilities_response.json()["services"][0]
    assert "objective" in capabilities_response.json()["agents"][0]
    assert ingest_response.status_code == 200
    assert ingest_response.json()["status"] == "queued"


def test_artifact_listing_endpoints_return_persisted_objects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        _build_full_stack(artifact_root=artifact_root)

        hypotheses_response = client.get("/hypotheses")
        proposals_response = client.get("/portfolio-proposals")
        paper_trades_response = client.get("/paper-trades/proposals")

        assert hypotheses_response.status_code == 200
        assert hypotheses_response.json()["total"] >= 1
        assert proposals_response.status_code == 200
        assert proposals_response.json()["total"] >= 1
        assert paper_trades_response.status_code == 200
        assert paper_trades_response.json()["total"] >= 1
    finally:
        get_settings.cache_clear()


def test_operator_review_endpoints_return_queue_context_and_apply_actions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        _build_full_stack(artifact_root=artifact_root)

        queue_response = client.get("/reviews/queue")
        assert queue_response.status_code == 200
        assert queue_response.json()["total"] >= 4

        research_brief_path = next((artifact_root / "research" / "research_briefs").glob("*.json"))
        brief_id = json.loads(research_brief_path.read_text(encoding="utf-8"))["research_brief_id"]
        signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
        signal_id = json.loads(signal_path.read_text(encoding="utf-8"))["signal_id"]

        context_response = client.get(f"/reviews/context/research_brief/{brief_id}")
        assert context_response.status_code == 200
        assert context_response.json()["research_brief"]["research_brief_id"] == brief_id
        assert context_response.json()["hypothesis"] is not None
        assert context_response.json()["supporting_evidence_links"]

        note_response = client.post(
            "/reviews/notes",
            json={
                "target_type": "research_brief",
                "target_id": brief_id,
                "author_id": "analyst_1",
                "body": "Explicitly call out remaining demand uncertainty.",
            },
        )
        assert note_response.status_code == 200
        assert note_response.json()["review_note"]["target_id"] == brief_id

        action_response = client.post(
            "/reviews/actions",
            json={
                "target_type": "signal",
                "target_id": signal_id,
                "reviewer_id": "pm_1",
                "outcome": "approve",
                "rationale": "Signal is ready for approved candidate handling.",
            },
        )
        assert action_response.status_code == 200
        assert action_response.json()["updated_target"]["status"] == "approved"
        assert action_response.json()["audit_log"]["status_before"] == "candidate"
        assert action_response.json()["audit_log"]["status_after"] == "approved"
    finally:
        get_settings.cache_clear()


def _build_full_stack(*, artifact_root: Path) -> None:
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
    run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )
    run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        assumed_reference_prices={"APEX": 102.0},
        clock=FrozenClock(FIXED_NOW),
    )


def _backtest_config() -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id(
            "btcfg",
            "text_only_candidate_signal",
            "2026-03-17",
            "2026-03-30",
            "5.0",
            "2.0",
        ),
        strategy_name="day6_text_signal_exploratory",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", "5.0", "2.0", "lag1"),
            transaction_cost_bps=5.0,
            slippage_bps=2.0,
            execution_lag_bars=1,
            decision_price_field="close",
            execution_price_field="open",
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
