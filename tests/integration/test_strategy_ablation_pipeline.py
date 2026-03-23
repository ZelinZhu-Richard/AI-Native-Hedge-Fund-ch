from __future__ import annotations

import json
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
    build_strategy_specs,
    load_strategy_inputs,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_strategy_ablation_pipeline_persists_all_variant_and_experiment_artifacts(
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
    strategy_inputs = load_strategy_inputs(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
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
        workflow_run_id="ablation_integration_test",
    )
    strategy_variants = build_default_strategy_variants(
        strategy_specs=strategy_specs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="ablation_integration_test",
    )

    response = run_strategy_ablation_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "ablation",
        experiment_root=artifact_root / "experiments",
        evaluation_root=artifact_root / "evaluation",
        price_fixture_path=PRICE_FIXTURE_PATH,
        ablation_config=_ablation_config(
            strategy_variants=strategy_variants,
            company_id=strategy_inputs.company_id,
        ),
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.experiment is not None
    assert response.evaluation_report is not None
    assert response.comparison_summary is not None
    assert response.experiment_scorecard is not None
    assert len(response.variant_backtest_runs) == 4
    assert all(run.experiment_id is not None for run in response.variant_backtest_runs)
    assert {spec.family for spec in response.strategy_specs} == {
        StrategyFamily.NAIVE_BASELINE,
        StrategyFamily.PRICE_ONLY_BASELINE,
        StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
        StrategyFamily.COMBINED_BASELINE,
    }
    assert all("winner" not in note.lower() for note in response.notes + response.ablation_result.notes)

    strategy_variant_paths = list((artifact_root / "ablation" / "strategy_variants").glob("*.json"))
    assert len(strategy_variant_paths) == 4
    variant_signal_dirs = list((artifact_root / "ablation" / "variant_signals").glob("*"))
    assert len(variant_signal_dirs) == 4
    assert all((directory / "signals").exists() for directory in variant_signal_dirs)
    assert (
        artifact_root
        / "ablation"
        / "ablation_results"
        / f"{response.ablation_result.ablation_result_id}.json"
    ).exists()
    assert (
        artifact_root
        / "experiments"
        / "experiments"
        / f"{response.experiment.experiment_id}.json"
    ).exists()
    assert (
        artifact_root
        / "evaluation"
        / "reports"
        / f"{response.evaluation_report.evaluation_report_id}.json"
    ).exists()
    assert (
        artifact_root
        / "evaluation"
        / "comparison_summaries"
        / f"{response.comparison_summary.comparison_summary_id}.json"
    ).exists()
    assert (
        artifact_root
        / "reporting"
        / "experiment_scorecards"
        / f"{response.experiment_scorecard.experiment_scorecard_id}.json"
    ).exists()

    experiment_payload = json.loads(
        (
            artifact_root
            / "experiments"
            / "experiments"
            / f"{response.experiment.experiment_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert experiment_payload["status"] == "completed"
    assert experiment_payload["dataset_reference_ids"]
    assert experiment_payload["experiment_artifact_ids"]
    assert experiment_payload["experiment_metric_ids"]
    experiment_artifact_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((artifact_root / "experiments" / "experiment_artifacts").glob("*.json"))
    ]
    assert {"SignalBundle", "ArbitrationDecision", "ExperimentScorecard"}.issubset(
        {payload["artifact_type"] for payload in experiment_artifact_payloads}
    )

    evaluation_payload = json.loads(
        (
            artifact_root
            / "evaluation"
            / "reports"
            / f"{response.evaluation_report.evaluation_report_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert evaluation_payload["target_id"] == response.ablation_result.ablation_result_id
    assert evaluation_payload["comparison_summary_id"] == response.comparison_summary.comparison_summary_id
    assert evaluation_payload["metric_ids"]
    assert evaluation_payload["robustness_check_ids"]

    comparison_payload = json.loads(
        (
            artifact_root
            / "evaluation"
            / "comparison_summaries"
            / f"{response.comparison_summary.comparison_summary_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert comparison_payload["expected_family_count"] == 4
    assert comparison_payload["observed_family_count"] == 4
    assert comparison_payload["ordered_strategy_variant_ids"] == [
        result["strategy_variant_id"] for result in response.ablation_result.model_dump()["variant_results"]
    ]
    assert comparison_payload["mechanical_order_only"] is True
    assert all("winner" not in note.lower() for note in comparison_payload["notes"])


def _ablation_config(
    *, strategy_variants: list[StrategyVariant], company_id: str
) -> AblationConfig:
    return AblationConfig(
        ablation_config_id=make_canonical_id("abcfg", "day9", "integration"),
        name="day9_apex_strategy_ablation",
        strategy_variants=strategy_variants,
        evaluation_slice=EvaluationSlice(
            evaluation_slice_id=make_canonical_id("eslice", "day9", "integration"),
            company_id=company_id,
            test_start=date(2026, 3, 17),
            test_end=date(2026, 3, 30),
            decision_frequency="daily",
            price_fixture_path=str(PRICE_FIXTURE_PATH),
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        shared_backtest_config=BacktestConfig(
            backtest_config_id=make_canonical_id("btcfg", "day9", "integration"),
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
        ),
        comparison_metric_name="net_pnl",
        requested_by="integration_test",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
