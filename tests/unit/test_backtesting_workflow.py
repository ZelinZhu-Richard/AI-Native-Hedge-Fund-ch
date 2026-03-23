from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
    RealismWarningKind,
    SignalStatus,
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
from pipelines.signal_generation import run_feature_signal_pipeline
from services.backtesting.loaders import load_backtest_inputs
from services.backtesting.simulation import run_backtest_simulation

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_backtesting_workflow_generates_run_events_and_benchmarks(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)

    response = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.backtest_run.exploratory_only is True
    assert response.strategy_decisions
    assert response.simulation_events
    assert response.decision_cutoffs
    assert all(decision.decision_cutoff is not None for decision in response.strategy_decisions)
    assert response.performance_summary.trade_count >= 1
    assert {benchmark.benchmark_kind for benchmark in response.benchmark_references} == {
        BenchmarkKind.FLAT_BASELINE,
        BenchmarkKind.BUY_AND_HOLD,
    }
    assert response.execution_timing_rule is not None
    assert response.fill_assumption is not None
    assert response.cost_model is not None
    assert response.realism_warnings
    assert response.backtest_run.execution_timing_rule_id == response.execution_timing_rule.execution_timing_rule_id
    assert response.backtest_run.fill_assumption_id == response.fill_assumption.fill_assumption_id
    assert response.backtest_run.cost_model_id == response.cost_model.cost_model_id
    assert {warning.warning_kind for warning in response.realism_warnings} >= {
        RealismWarningKind.SYNTHETIC_PRICE_FIXTURE,
        RealismWarningKind.UNIT_POSITION_SIMPLIFICATION,
        RealismWarningKind.FIXED_BPS_COSTS,
        RealismWarningKind.NO_INTRADAY_MICROSTRUCTURE,
    }


def test_backtesting_workflow_records_experiment_registry(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)

    response = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.experiment is not None
    assert response.experiment_config is not None
    assert response.backtest_run.experiment_id == response.experiment.experiment_id
    assert len(response.dataset_references) == 2
    assert response.experiment_artifacts
    assert response.experiment_metrics
    assert {artifact.artifact_type for artifact in response.experiment_artifacts} >= {
        "SignalBundle",
        "ArbitrationDecision",
    }
    assert {reference.data_snapshot_id for reference in response.dataset_references} == {
        snapshot.data_snapshot_id for snapshot in response.data_snapshots
    }
    assert (
        artifact_root
        / "experiments"
        / "experiments"
        / f"{response.experiment.experiment_id}.json"
    ).exists()
    assert (
        artifact_root
        / "experiments"
        / "experiment_configs"
        / f"{response.experiment_config.experiment_config_id}.json"
    ).exists()

    metric_source_ids = {metric.source_artifact_id for metric in response.experiment_metrics}
    assert response.performance_summary.performance_summary_id in metric_source_ids
    assert {
        benchmark.benchmark_reference_id for benchmark in response.benchmark_references
    }.issubset(metric_source_ids)
    snapshot_uris = {
        (artifact_root / "backtesting" / "snapshots" / f"{snapshot.data_snapshot_id}.json")
        .resolve()
        .as_uri()
        for snapshot in response.data_snapshots
    }
    assert {reference.storage_uri for reference in response.dataset_references} == snapshot_uris
    assert all(
        snapshot.information_cutoff_time == response.decision_cutoffs[-1].decision_time
        for snapshot in response.data_snapshots
    )


def test_backtesting_experiment_config_is_stable_for_identical_runs(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)
    config = _backtest_config()

    first = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=artifact_root / "backtesting_one",
        experiment_root=artifact_root / "experiments_one",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=config,
        clock=FrozenClock(FIXED_NOW),
    )
    second = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=artifact_root / "backtesting_two",
        experiment_root=artifact_root / "experiments_two",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=config,
        clock=FrozenClock(FIXED_NOW),
    )

    assert first.experiment_config is not None
    assert second.experiment_config is not None
    assert first.experiment_config.parameter_hash == second.experiment_config.parameter_hash
    assert first.experiment_config.experiment_config_id == second.experiment_config.experiment_config_id


def test_backtest_pipeline_uses_custom_workspace_defaults_for_experiment_registry(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "custom_workspace"
    signal_root = _build_signal_artifacts(artifact_root=workspace_root)

    response = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.experiment is not None
    assert (workspace_root / "backtesting" / "runs").exists()
    assert (
        workspace_root
        / "experiments"
        / "experiments"
        / f"{response.experiment.experiment_id}.json"
    ).exists()


def test_future_feature_availability_blocks_signal_use(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)
    feature_path = next((signal_root / "features").glob("*.json"))
    payload = json.loads(feature_path.read_text(encoding="utf-8"))
    payload["feature_value"]["available_at"] = "2026-03-24T20:00:00Z"
    payload["feature_value"]["availability_window"]["available_from"] = "2026-03-24T20:00:00Z"
    feature_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    response = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(test_end=date(2026, 3, 20)),
        clock=FrozenClock(FIXED_NOW),
    )

    assert all(decision.signal_id is None for decision in response.strategy_decisions)
    assert all(event.event_type.value != "fill" for event in response.simulation_events)
    assert any(
        check.startswith("future_feature_availability_rejected")
        for check in response.backtest_run.leakage_checks
    )


def test_missing_signal_availability_window_blocks_backtest(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)
    signal_path = next((signal_root / "signals").glob("*.json"))
    payload = json.loads(signal_path.read_text(encoding="utf-8"))
    payload["availability_window"] = None
    signal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    try:
        run_backtest_pipeline(
            signal_root=signal_root,
            feature_root=signal_root,
            output_root=artifact_root / "backtesting",
            price_fixture_path=PRICE_FIXTURE_PATH,
            backtest_config=_backtest_config(),
            clock=FrozenClock(FIXED_NOW),
        )
    except ValueError as exc:
        assert "timing-safe availability" in str(exc)
    else:
        raise AssertionError("Expected missing signal availability metadata to block the backtest.")


def test_execution_lag_and_costs_reduce_net_pnl(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)

    response = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )

    decision_event = next(
        event for event in response.simulation_events if event.event_type.value == "decision"
    )
    fill_event = next(event for event in response.simulation_events if event.event_type.value == "fill")
    assert fill_event.event_time > decision_event.event_time
    assert fill_event.event_time == datetime(2026, 3, 18, 13, 30, tzinfo=UTC)
    assert fill_event.price == 101.2
    assert response.performance_summary.net_pnl < response.performance_summary.gross_pnl


def test_transaction_costs_reduce_net_pnl(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)
    inputs = load_backtest_inputs(
        signal_root=signal_root,
        feature_root=signal_root,
        price_fixture_path=PRICE_FIXTURE_PATH,
    )

    zero_cost = run_backtest_simulation(
        inputs=inputs,
        config=_backtest_config(transaction_cost_bps=0.0, slippage_bps=0.0),
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="btrun_zero",
        backtest_run_id="btrun_zero",
    )
    with_cost = run_backtest_simulation(
        inputs=inputs,
        config=_backtest_config(transaction_cost_bps=10.0, slippage_bps=5.0),
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="btrun_cost",
        backtest_run_id="btrun_cost",
    )

    assert with_cost.performance_summary.net_pnl < zero_cost.performance_summary.net_pnl


def test_backtest_simulation_is_reproducible_for_fixed_inputs(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    signal_root = _build_signal_artifacts(artifact_root=artifact_root)
    inputs = load_backtest_inputs(
        signal_root=signal_root,
        feature_root=signal_root,
        price_fixture_path=PRICE_FIXTURE_PATH,
    )
    config = _backtest_config()

    first = run_backtest_simulation(
        inputs=inputs,
        config=config,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="btrun_replay",
        backtest_run_id="btrun_replay",
    )
    second = run_backtest_simulation(
        inputs=inputs,
        config=config,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="btrun_replay",
        backtest_run_id="btrun_replay",
    )

    assert [
        (decision.decision_time, decision.action, decision.target_units, decision.signal_id)
        for decision in first.strategy_decisions
    ] == [
        (decision.decision_time, decision.action, decision.target_units, decision.signal_id)
        for decision in second.strategy_decisions
    ]
    assert first.performance_summary.model_dump() == second.performance_summary.model_dump()


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


def _backtest_config(
    *,
    test_start: date = date(2026, 3, 17),
    test_end: date = date(2026, 3, 30),
    transaction_cost_bps: float = 5.0,
    slippage_bps: float = 2.0,
) -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id(
            "btcfg",
            "text_only_candidate_signal",
            test_start.isoformat(),
            test_end.isoformat(),
            str(transaction_cost_bps),
            str(slippage_bps),
        ),
        strategy_name="day6_text_signal_exploratory",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=test_start,
        test_end=test_end,
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id(
                "exec",
                str(transaction_cost_bps),
                str(slippage_bps),
                "lag1",
            ),
            transaction_cost_bps=transaction_cost_bps,
            slippage_bps=slippage_bps,
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
