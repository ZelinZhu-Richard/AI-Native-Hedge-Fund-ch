from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeVar, cast

import pytest

from libraries.schemas import (
    AblationView,
    AlertRecord,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
    PortfolioProposal,
    ProvenanceRecord,
    ReviewOutcome,
    ReviewTargetType,
    RunSummary,
    StrictModel,
    WorkflowStatus,
)
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
from services.ingestion import FixtureIngestionRequest, IngestionService
from services.monitoring import MonitoringService, RunHealthChecksRequest
from services.operator_review import ApplyReviewActionRequest, OperatorReviewService

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 19, 11, 0, tzinfo=UTC)
TModel = TypeVar("TModel", bound=StrictModel)


def test_run_health_checks_produces_structured_outputs(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    monitoring_service = MonitoringService(clock=FrozenClock(FIXED_NOW))

    response = monitoring_service.run_health_checks(
        RunHealthChecksRequest(
            artifact_root=artifact_root,
            monitoring_root=artifact_root / "monitoring",
            review_root=artifact_root / "review",
        )
    )

    assert {check.check_name for check in response.health_checks} >= {
        "artifact_root_resolved",
        "monitoring_storage_available",
        "service_registry_loaded",
        "review_storage_readable",
        "recent_open_alerts_present",
    }
    assert any(status.service_name == "monitoring" for status in response.service_statuses)
    assert (artifact_root / "monitoring" / "health_checks").exists()
    assert (artifact_root / "monitoring" / "alert_conditions").exists()


def test_failed_ingestion_creates_failed_run_summary_and_alert(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    service = IngestionService(clock=FrozenClock(FIXED_NOW))

    with pytest.raises(FileNotFoundError):
        service.ingest_fixture(
            FixtureIngestionRequest(
                fixture_path=tmp_path / "missing_fixture.json",
                output_root=artifact_root / "ingestion",
                requested_by="unit_test",
            )
        )

    run_summaries = _load_models(artifact_root / "monitoring" / "run_summaries", RunSummary)
    alerts = _load_models(artifact_root / "monitoring" / "alert_records", AlertRecord)

    assert len(run_summaries) == 1
    assert run_summaries[0].workflow_name == "fixture_ingestion"
    assert run_summaries[0].status is WorkflowStatus.FAILED
    assert alerts
    assert alerts[0].workflow_run_id == run_summaries[0].workflow_run_id


def test_successful_evidence_extraction_creates_run_summaries(tmp_path: Path) -> None:
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

    run_summaries = _load_models(artifact_root / "monitoring" / "run_summaries", RunSummary)
    extraction_summaries = [
        summary for summary in run_summaries if summary.workflow_name == "evidence_extraction"
    ]

    assert extraction_summaries
    assert all(summary.status is WorkflowStatus.SUCCEEDED for summary in extraction_summaries)
    assert all(summary.produced_artifact_counts for summary in extraction_summaries)


def test_review_action_creates_run_summary_with_audit_linkage(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_full_stack(artifact_root=artifact_root)
    proposal = _load_single_model(
        artifact_root / "portfolio" / "portfolio_proposals",
        PortfolioProposal,
    )

    response = OperatorReviewService(clock=FrozenClock(FIXED_NOW)).apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=proposal.portfolio_proposal_id,
            reviewer_id="risk_1",
            outcome=ReviewOutcome.NEEDS_REVISION,
            rationale="Proposal remains review-bound.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )

    run_summaries = _load_models(artifact_root / "monitoring" / "run_summaries", RunSummary)
    review_summaries = [
        summary for summary in run_summaries if summary.workflow_name == "review_action"
    ]

    assert review_summaries
    assert response.review_decision.review_decision_id in review_summaries[-1].produced_artifact_ids
    assert response.audit_log.audit_log_id in review_summaries[-1].produced_artifact_ids


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
            "2026-03-19",
            "2026-03-31",
            "5.0",
            "2.0",
        ),
        strategy_name="day6_text_signal_exploratory",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 19),
        test_end=date(2026, 3, 31),
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


def _load_models(directory: Path, model_cls: type[TModel]) -> list[TModel]:
    return [
        cast(TModel, model_cls.model_validate_json(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.json"))
    ]


def _load_single_model(directory: Path, model_cls: type[TModel]) -> TModel:
    return cast(
        TModel,
        model_cls.model_validate_json(next(directory.glob("*.json")).read_text(encoding="utf-8")),
    )
