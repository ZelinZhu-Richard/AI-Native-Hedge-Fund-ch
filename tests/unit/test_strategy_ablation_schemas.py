from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    AblationConfig,
    AblationResult,
    AblationVariantResult,
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    DerivedArtifactValidationStatus,
    EvaluationSlice,
    ExecutionAssumption,
    ProvenanceRecord,
    ResearchStance,
    SignalStatus,
    StrategyFamily,
    StrategySpec,
    StrategyVariant,
    StrategyVariantSignal,
)
from libraries.time import FrozenClock
from services.backtesting.ablation import build_strategy_specs

FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_strategy_spec_requires_required_inputs() -> None:
    with pytest.raises(ValidationError):
        StrategySpec(
            strategy_spec_id="sspec_test",
            name="price_only_baseline",
            family=StrategyFamily.PRICE_ONLY_BASELINE,
            description="Synthetic spec.",
            signal_family="price_only_momentum_3bar",
            required_inputs=[],
            decision_rule_name="three_bar_close_momentum",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_strategy_variant_signal_requires_snapshot_and_ordered_window() -> None:
    with pytest.raises(ValidationError):
        StrategyVariantSignal(
            strategy_variant_signal_id="vsig_test",
            strategy_variant_id="svar_test",
            company_id="co_test",
            signal_family="price_only_momentum_3bar",
            family=StrategyFamily.PRICE_ONLY_BASELINE,
            ablation_view=AblationView.PRICE_ONLY,
            stance=ResearchStance.POSITIVE,
            primary_score=0.42,
            effective_at=FIXED_NOW,
            expires_at=FIXED_NOW.replace(hour=10),
            status=SignalStatus.CANDIDATE,
            validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
            summary="Synthetic variant signal.",
            source_snapshot_ids=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_ablation_config_requires_multiple_variants() -> None:
    specs = build_strategy_specs(
        families=[StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE],
        clock=_clock(),
        workflow_run_id="ablation_test",
    )
    variant = StrategyVariant(
        strategy_variant_id="svar_text_only",
        strategy_spec_id=specs[0].strategy_spec_id,
        variant_name="text_only_candidate_baseline",
        family=StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    with pytest.raises(ValidationError):
        AblationConfig(
            ablation_config_id="abcfg_test",
            name="test_ablation",
            strategy_variants=[variant],
            evaluation_slice=_evaluation_slice(),
            shared_backtest_config=_backtest_config(),
            comparison_metric_name="net_pnl",
            requested_by="unit_test",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_ablation_result_requires_multiple_rows() -> None:
    with pytest.raises(ValidationError):
        AblationResult(
            ablation_result_id="abres_test",
            ablation_config_id="abcfg_test",
            evaluation_slice_id="eslice_test",
            variant_results=[_variant_result("svar_one")],
            comparison_metric_name="net_pnl",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def _variant_result(strategy_variant_id: str) -> AblationVariantResult:
    return AblationVariantResult(
        strategy_variant_id=strategy_variant_id,
        family=StrategyFamily.NAIVE_BASELINE,
        variant_signal_ids=["vsig_test"],
        backtest_run_id="btrun_test",
        experiment_id="exp_test",
        performance_summary_id="psum_test",
        benchmark_reference_ids=["bench_test"],
        dataset_reference_ids=["dref_test"],
        gross_pnl=0.0,
        net_pnl=0.0,
        trade_count=0,
        turnover_notional=0.0,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _evaluation_slice() -> EvaluationSlice:
    return EvaluationSlice(
        evaluation_slice_id="eslice_test",
        company_id="co_test",
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        decision_frequency="daily",
        price_fixture_path="/tmp/apex_prices.json",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _backtest_config() -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id="btcfg_test",
        strategy_name="shared_ablation_backtest",
        signal_family="shared_ablation_signal_family",
        ablation_view=AblationView.COMBINED,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id="exec_test",
            transaction_cost_bps=5.0,
            slippage_bps=2.0,
            execution_lag_bars=1,
            decision_price_field="close",
            execution_price_field="open",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)


def _clock() -> FrozenClock:
    return FrozenClock(FIXED_NOW)
