from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient

from apps.api.main import app
from libraries.config import get_settings
from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
    ReviewOutcome,
)
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
DEMO_TIME = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


def test_api_health_version_and_alias_routes() -> None:
    health_response = client.get("/system/health")
    alias_response = client.get("/health")
    version_response = client.get("/system/version")

    assert health_response.status_code == 200
    assert health_response.json()["data"]["status"] == "ok"
    assert alias_response.status_code == 200
    assert alias_response.json()["data"] == health_response.json()["data"]
    assert version_response.status_code == 200
    assert version_response.json()["data"]["version"] == "0.1.0"


def test_system_manifest_and_capabilities_are_structured() -> None:
    capabilities_response = client.get("/system/capabilities")
    manifest_response = client.get("/system/manifest")
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
    descriptors = capabilities_response.json()["data"]["items"]
    assert any(item["kind"] == "service" and item["name"] == "monitoring" for item in descriptors)
    assert any(item["kind"] == "agent" for item in descriptors)
    assert any(item["kind"] == "workflow" and item["name"] == "demo_end_to_end" for item in descriptors)

    assert manifest_response.status_code == 200
    manifest = manifest_response.json()["data"]
    assert manifest["project_name"] == "ANHF Research OS"
    assert "ARTIFACT_ROOT" in manifest["config_surface"]
    assert any(item["warning_code"] == "local_only" for item in manifest["warnings"])

    assert ingest_response.status_code == 200
    assert ingest_response.json()["data"]["status"] == "queued"


def test_monitoring_api_endpoints_return_structured_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        _build_full_stack(artifact_root=artifact_root)

        health_details_response = client.get("/system/health/details")
        run_summaries_response = client.get("/monitoring/run-summaries/recent")
        failure_summaries_response = client.get("/monitoring/failures/recent")
        service_status_response = client.get("/monitoring/services")

        assert health_details_response.status_code == 200
        assert health_details_response.json()["data"]["health_checks"]
        assert service_status_response.status_code == 200
        assert service_status_response.json()["data"]["total"] >= 1
        assert any(
            item["service_name"] == "monitoring"
            for item in service_status_response.json()["data"]["items"]
        )
        assert run_summaries_response.status_code == 200
        assert run_summaries_response.json()["data"]["total"] >= 1
        assert failure_summaries_response.status_code == 200
        assert "run_summaries" in failure_summaries_response.json()["data"]
        assert "alert_records" in failure_summaries_response.json()["data"]
    finally:
        get_settings.cache_clear()


def test_artifact_and_report_listing_endpoints_return_persisted_objects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        _build_full_stack(artifact_root=artifact_root, approve_proposal=True)

        hypotheses_response = client.get("/research/hypotheses")
        hypotheses_alias_response = client.get("/hypotheses")
        briefs_response = client.get("/research/briefs")
        proposals_response = client.get("/portfolio/proposals")
        proposals_alias_response = client.get("/portfolio-proposals")
        paper_trades_response = client.get("/portfolio/paper-trades")
        paper_trades_alias_response = client.get("/paper-trades/proposals")

        assert hypotheses_response.status_code == 200
        assert hypotheses_response.json()["data"]["total"] >= 1
        assert hypotheses_alias_response.json()["data"] == hypotheses_response.json()["data"]
        assert briefs_response.status_code == 200
        assert briefs_response.json()["data"]["total"] >= 1

        assert proposals_response.status_code == 200
        assert proposals_response.json()["data"]["total"] >= 1
        assert proposals_alias_response.json()["data"] == proposals_response.json()["data"]
        proposal_id = proposals_response.json()["data"]["items"][0]["portfolio_proposal_id"]

        assert paper_trades_response.status_code == 200
        assert paper_trades_response.json()["data"]["total"] >= 1
        assert paper_trades_alias_response.json()["data"] == paper_trades_response.json()["data"]

        proposal_scorecard_response = client.get(f"/reports/proposals/{proposal_id}/scorecard")
        assert proposal_scorecard_response.status_code == 200
        assert (
            proposal_scorecard_response.json()["data"]["portfolio_proposal_id"] == proposal_id
        )
    finally:
        get_settings.cache_clear()


def test_operator_review_endpoints_use_envelopes_and_structured_errors(
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
        assert queue_response.json()["data"]["total"] >= 3

        research_brief_path = next((artifact_root / "research" / "research_briefs").glob("*.json"))
        brief_id = json.loads(research_brief_path.read_text(encoding="utf-8"))["research_brief_id"]
        signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
        signal_id = json.loads(signal_path.read_text(encoding="utf-8"))["signal_id"]

        context_response = client.get(f"/reviews/context/research_brief/{brief_id}")
        assert context_response.status_code == 200
        assert context_response.json()["data"]["research_brief"]["research_brief_id"] == brief_id
        assert context_response.json()["data"]["hypothesis"] is not None
        assert context_response.json()["data"]["supporting_evidence_links"]

        not_found_response = client.get("/reviews/context/portfolio_proposal/missing_proposal")
        assert not_found_response.status_code == 404
        assert not_found_response.json()["status"] == "error"
        assert not_found_response.json()["error_code"] == "not_found"

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
        assert note_response.json()["data"]["review_note"]["target_id"] == brief_id

        action_response = client.post(
            "/reviews/actions",
            json={
                "target_type": "signal",
                "target_id": signal_id,
                "reviewer_id": "pm_1",
                "outcome": "needs_revision",
                "rationale": "Signal remains review-bound until it is validated.",
            },
        )
        assert action_response.status_code == 200
        assert action_response.json()["data"]["updated_target"]["status"] == "candidate"
        assert action_response.json()["data"]["audit_log"]["status_before"] == "candidate"
        assert action_response.json()["data"]["audit_log"]["status_after"] == "candidate"
    finally:
        get_settings.cache_clear()


def test_workflow_entrypoints_return_compact_invocation_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        demo_response = client.post(
            "/workflows/demo/run",
            json={
                "base_root": str(tmp_path / "demo_run"),
                "requested_by": "api_demo_test",
                "frozen_time": DEMO_TIME.isoformat().replace("+00:00", "Z"),
            },
        )
        assert demo_response.status_code == 200
        demo_data = demo_response.json()["data"]
        assert demo_data["workflow_name"] == "demo_end_to_end"
        assert demo_data["demo_run_id"]
        assert Path(demo_data["manifest_path"]).exists()

        daily_response = client.post(
            "/workflows/daily/run",
            json={
                "artifact_root": str(tmp_path / "daily_run"),
                "fixtures_root": str(FIXTURE_ROOT),
                "requested_by": "api_daily_test",
            },
        )
        assert daily_response.status_code == 200
        daily_data = daily_response.json()["data"]
        assert daily_data["workflow_name"] == "daily_workflow"
        assert daily_data["workflow_run_id"]
        assert daily_data["artifact_root"] == str(tmp_path / "daily_run")
    finally:
        get_settings.cache_clear()


def _build_full_stack(*, artifact_root: Path, approve_proposal: bool = False) -> None:
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
        proposal_review_outcome=(ReviewOutcome.APPROVE if approve_proposal else None),
        reviewer_id=("api_test_reviewer" if approve_proposal else None),
        review_notes=(["Approved for paper-trade candidate creation."] if approve_proposal else None),
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
