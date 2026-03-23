from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
    ProvenanceRecord,
    ReviewOutcome,
    SignalStatus,
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
from services.backtest_reconciliation import (
    BacktestReconciliationService,
    RunBacktestPaperReconciliationRequest,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)


def test_reconciliation_requires_explicit_backtest_run_id_when_multiple_runs_exist(
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
    run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(name_suffix="one"),
        clock=FrozenClock(FIXED_NOW),
    )
    run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(name_suffix="two"),
        clock=FrozenClock(FIXED_NOW),
    )
    proposal_response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_test",
        review_notes=["Approved for paper-trade candidate creation."],
        assumed_reference_prices={"APEX": 103.0},
        clock=FrozenClock(FIXED_NOW),
    )

    with pytest.raises(ValueError, match="explicit backtest_run_id"):
        BacktestReconciliationService(clock=FrozenClock(FIXED_NOW)).run_backtest_paper_reconciliation(
            RunBacktestPaperReconciliationRequest(
                backtesting_root=artifact_root / "backtesting",
                portfolio_root=artifact_root / "portfolio",
                review_root=artifact_root / "review",
                experiments_root=artifact_root / "experiments",
                monitoring_root=artifact_root / "monitoring",
                output_root=artifact_root / "reconciliation",
                portfolio_proposal_id=proposal_response.final_portfolio_proposal.portfolio_proposal_id,
                requested_by="unit_test",
            )
        )


def _backtest_config(*, name_suffix: str) -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id(
            "btcfg",
            f"text_only_candidate_signal_{name_suffix}",
            "2026-03-17",
            "2026-03-30",
            "5.0",
            "2.0",
        ),
        strategy_name=f"day6_text_signal_exploratory_{name_suffix}",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", name_suffix, "5.0", "2.0", "lag1"),
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
