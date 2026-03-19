from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    AblationConfig,
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    EvaluationSlice,
    ExecutionAssumption,
    ProvenanceRecord,
    ResearchStance,
    SignalStatus,
    StrategyFamily,
    StrategyVariant,
)
from libraries.time import FrozenClock
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_strategy_ablation_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import run_feature_signal_pipeline
from services.backtesting.ablation import (
    build_default_strategy_variants,
    build_strategy_input_snapshots,
    build_strategy_specs,
    load_strategy_inputs,
    materialize_variant_signals,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_variant_materialization_supports_all_day9_families(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)
    strategy_inputs = load_strategy_inputs(
        signal_root=signal_root,
        feature_root=signal_root,
        price_fixture_path=PRICE_FIXTURE_PATH,
    )
    strategy_specs = build_strategy_specs(
        families=[
            StrategyFamily.NAIVE_BASELINE,
            StrategyFamily.PRICE_ONLY_BASELINE,
            StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
            StrategyFamily.COMBINED_BASELINE,
        ],
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_variant_test",
    )
    strategy_variants = build_default_strategy_variants(
        strategy_specs=strategy_specs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_variant_test",
    )
    source_snapshots = build_strategy_input_snapshots(
        inputs=strategy_inputs,
        evaluation_slice=_ablation_config(
            strategy_variants, company_id=strategy_inputs.company_id
        ).evaluation_slice,
        ablation_config_id="abcfg_variant_test",
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_variant_test",
    )
    variant_by_family = {variant.family: variant for variant in strategy_variants}

    naive = materialize_variant_signals(
        inputs=strategy_inputs,
        variant=variant_by_family[StrategyFamily.NAIVE_BASELINE],
        evaluation_slice=_ablation_config(
            strategy_variants, company_id=strategy_inputs.company_id
        ).evaluation_slice,
        source_snapshots=source_snapshots,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_variant_test",
    )
    text_only = materialize_variant_signals(
        inputs=strategy_inputs,
        variant=variant_by_family[StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE],
        evaluation_slice=_ablation_config(
            strategy_variants, company_id=strategy_inputs.company_id
        ).evaluation_slice,
        source_snapshots=source_snapshots,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_variant_test",
    )
    price_only = materialize_variant_signals(
        inputs=strategy_inputs,
        variant=variant_by_family[StrategyFamily.PRICE_ONLY_BASELINE],
        evaluation_slice=_ablation_config(
            strategy_variants, company_id=strategy_inputs.company_id
        ).evaluation_slice,
        source_snapshots=source_snapshots,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_variant_test",
    )
    combined = materialize_variant_signals(
        inputs=strategy_inputs,
        variant=variant_by_family[StrategyFamily.COMBINED_BASELINE],
        evaluation_slice=_ablation_config(
            strategy_variants, company_id=strategy_inputs.company_id
        ).evaluation_slice,
        source_snapshots=source_snapshots,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_variant_test",
    )

    assert len(naive.signals) == 1
    assert naive.signals[0].stance is ResearchStance.MONITOR
    assert naive.signals[0].primary_score == 0.0

    assert text_only.signals
    assert len(text_only.signals) == len(strategy_inputs.text_signals)
    assert all(signal.source_signal_ids for signal in text_only.signals)
    assert {signal.effective_at for signal in text_only.signals} == {
        signal.effective_at for signal in strategy_inputs.text_signals
    }

    assert len(price_only.signals) == 7
    assert price_only.signals[0].effective_at == datetime(2026, 3, 20, 20, 0, tzinfo=UTC)

    assert combined.signals
    assert combined.signals[0].effective_at >= price_only.signals[0].effective_at
    assert all(signal.source_signal_ids for signal in combined.signals)


def test_strategy_ablation_workflow_records_child_and_parent_experiments(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)
    strategy_inputs = load_strategy_inputs(
        signal_root=signal_root,
        feature_root=signal_root,
        price_fixture_path=PRICE_FIXTURE_PATH,
    )
    strategy_specs = build_strategy_specs(
        families=[
            StrategyFamily.NAIVE_BASELINE,
            StrategyFamily.PRICE_ONLY_BASELINE,
            StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
            StrategyFamily.COMBINED_BASELINE,
        ],
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_workflow_test",
    )
    strategy_variants = build_default_strategy_variants(
        strategy_specs=strategy_specs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_workflow_test",
    )

    response = run_strategy_ablation_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=artifact_root / "ablation",
        experiment_root=artifact_root / "experiments",
        evaluation_root=artifact_root / "evaluation",
        price_fixture_path=PRICE_FIXTURE_PATH,
        ablation_config=_ablation_config(
            strategy_variants, company_id=strategy_inputs.company_id
        ),
        clock=FrozenClock(FIXED_NOW),
    )

    assert {spec.family for spec in response.strategy_specs} == {
        StrategyFamily.NAIVE_BASELINE,
        StrategyFamily.PRICE_ONLY_BASELINE,
        StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
        StrategyFamily.COMBINED_BASELINE,
    }
    assert len(response.variant_backtest_runs) == 4
    assert all(run.experiment_id is not None for run in response.variant_backtest_runs)
    assert response.experiment is not None
    assert response.evaluation_report is not None
    assert response.comparison_summary is not None
    assert response.comparison_summary.expected_family_count == 4
    assert response.comparison_summary.observed_family_count == 4
    assert any(metric.metric_name == "strategy_family_coverage_ratio" for metric in response.evaluation_metrics)
    assert any(metric.metric_name == "experiment_linkage_ratio" for metric in response.evaluation_metrics)
    assert len(response.ablation_result.variant_results) == 4
    assert {result.backtest_run_id for result in response.ablation_result.variant_results} == {
        run.backtest_run_id for run in response.variant_backtest_runs
    }
    assert all(result.experiment_id is not None for result in response.ablation_result.variant_results)
    assert all("winner" not in note.lower() for note in response.ablation_result.notes)
    assert (artifact_root / "ablation" / "ablation_results").exists()
    assert (artifact_root / "evaluation" / "reports").exists()
    assert (
        artifact_root / "experiments" / "experiments" / f"{response.experiment.experiment_id}.json"
    ).exists()


def _build_signal_artifacts(*, artifact_root: Path) -> Path:
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
    return artifact_root / "signal_generation"


def _ablation_config(
    strategy_variants: list[StrategyVariant], *, company_id: str
) -> AblationConfig:
    return AblationConfig(
        ablation_config_id=make_canonical_id("abcfg", "day9", "apex"),
        name="day9_apex_baseline_ablation",
        strategy_variants=strategy_variants,
        evaluation_slice=_evaluation_slice(company_id=company_id),
        shared_backtest_config=_shared_backtest_config(),
        comparison_metric_name="net_pnl",
        requested_by="unit_test",
        notes=["Mechanical Day 9 ablation run."],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _evaluation_slice(*, company_id: str) -> EvaluationSlice:
    return EvaluationSlice(
        evaluation_slice_id=make_canonical_id("eslice", "day9", "apex"),
        company_id=company_id,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        decision_frequency="daily",
        price_fixture_path=str(PRICE_FIXTURE_PATH),
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _shared_backtest_config() -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id("btcfg", "day9_shared_ablation"),
        strategy_name="day9_shared_ablation_backtest",
        signal_family="shared_ablation_signal_family",
        ablation_view=AblationView.COMBINED,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", "5.0", "2.0", "lag1"),
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
