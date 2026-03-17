from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BacktestRun,
    BacktestStatus,
    BenchmarkKind,
    BenchmarkReference,
    DataLayer,
    DataSnapshot,
    DecisionAction,
    ExecutionAssumption,
    PerformanceSummary,
    ProvenanceRecord,
    SimulationEvent,
    SimulationEventType,
    StrategyDecision,
)

FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_data_snapshot_rejects_watermark_after_information_cutoff() -> None:
    with pytest.raises(ValidationError):
        DataSnapshot(
            data_snapshot_id="snap_test",
            dataset_name="candidate_signals",
            dataset_version="day6",
            data_layer=DataLayer.DERIVED,
            snapshot_time=FIXED_NOW,
            watermark_time=FIXED_NOW,
            information_cutoff_time=FIXED_NOW.replace(hour=10),
            storage_uri="file:///tmp/snapshot.json",
            schema_version="day6",
            created_by_process="unit_test",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_backtest_config_requires_non_empty_allowlist() -> None:
    with pytest.raises(ValidationError):
        BacktestConfig(
            backtest_config_id="btcfg_test",
            strategy_name="test_strategy",
            signal_family="text_only_candidate_signal",
            ablation_view=AblationView.TEXT_ONLY,
            test_start=date(2026, 3, 17),
            test_end=date(2026, 3, 30),
            signal_status_allowlist=[],
            execution_assumption=_execution_assumption(),
            benchmark_kinds=[BenchmarkKind.FLAT_BASELINE],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_strategy_decision_requires_signal_time_when_signal_is_present() -> None:
    with pytest.raises(ValidationError):
        StrategyDecision(
            strategy_decision_id="sdec_test",
            backtest_run_id="btrun_test",
            company_id="co_test",
            signal_id="sig_test",
            decision_time=FIXED_NOW,
            action=DecisionAction.OPEN_LONG,
            target_units=1,
            decision_snapshot_id="snap_test",
            reason="Synthetic decision.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_simulation_event_fill_requires_price_quantity_and_position() -> None:
    with pytest.raises(ValidationError):
        SimulationEvent(
            simulation_event_id="sevt_test",
            backtest_run_id="btrun_test",
            strategy_decision_id="sdec_test",
            event_type=SimulationEventType.FILL,
            event_time=FIXED_NOW,
            cash_delta=-101.0,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_backtest_run_requires_benchmark_and_allowed_signal_statuses() -> None:
    with pytest.raises(ValidationError):
        BacktestRun(
            backtest_run_id="btrun_test",
            backtest_config_id="btcfg_test",
            company_id="co_test",
            strategy_name="test_strategy",
            signal_family="text_only_candidate_signal",
            ablation_view=AblationView.TEXT_ONLY,
            status=BacktestStatus.COMPLETED,
            test_start=date(2026, 3, 17),
            test_end=date(2026, 3, 30),
            signal_snapshot_id="snap_sig",
            price_snapshot_id="snap_px",
            execution_assumption_id="exec_test",
            performance_summary_id="psum_test",
            benchmark_reference_ids=[],
            decision_cutoff_time=FIXED_NOW,
            allowed_signal_statuses=[],
            leakage_checks=["signal_snapshot_cutoff_check:passed"],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_performance_summary_accepts_cost_reduced_net_pnl() -> None:
    summary = PerformanceSummary(
        performance_summary_id="psum_test",
        backtest_run_id="btrun_test",
        starting_cash=100_000.0,
        ending_cash=99_995.0,
        gross_pnl=0.0,
        net_pnl=-5.0,
        trade_count=1,
        turnover_notional=101.2,
        benchmark_reference_ids=["bench_flat", "bench_bh"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert summary.net_pnl == -5.0


def test_benchmark_reference_validates_simple_payload() -> None:
    benchmark = BenchmarkReference(
        benchmark_reference_id="bench_test",
        backtest_run_id="btrun_test",
        benchmark_name="Flat Baseline",
        benchmark_kind=BenchmarkKind.FLAT_BASELINE,
        starting_value=100_000.0,
        ending_value=100_000.0,
        simple_return=0.0,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert benchmark.benchmark_kind is BenchmarkKind.FLAT_BASELINE


def _execution_assumption() -> ExecutionAssumption:
    return ExecutionAssumption(
        execution_assumption_id="exec_test",
        transaction_cost_bps=5.0,
        slippage_bps=2.0,
        execution_lag_bars=1,
        decision_price_field="close",
        execution_price_field="open",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
