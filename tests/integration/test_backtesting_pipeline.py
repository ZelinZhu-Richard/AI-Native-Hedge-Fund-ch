from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
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

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_backtesting_pipeline_persists_exploratory_artifacts(tmp_path: Path) -> None:
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

    response = run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )

    run_path = artifact_root / "backtesting" / "runs" / f"{response.backtest_run.backtest_run_id}.json"
    summary_path = (
        artifact_root
        / "backtesting"
        / "performance_summaries"
        / f"{response.performance_summary.performance_summary_id}.json"
    )
    assert run_path.exists()
    assert summary_path.exists()

    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    assert run_payload["exploratory_only"] is True
    assert run_payload["allowed_signal_statuses"] == [SignalStatus.CANDIDATE.value]

    assert response.strategy_decisions
    assert any(event.event_type.value == "fill" for event in response.simulation_events)
    assert all(
        decision.signal_effective_at is None or decision.decision_time >= decision.signal_effective_at
        for decision in response.strategy_decisions
    )

    signal_generation_root = artifact_root / "signal_generation"
    feature_payloads = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (signal_generation_root / "features").glob("*.json")
    }
    for decision in response.strategy_decisions:
        if decision.signal_id is None:
            continue
        signal_payload = json.loads(
            (signal_generation_root / "signals" / f"{decision.signal_id}.json").read_text(
                encoding="utf-8"
            )
        )
        for feature_id in signal_payload["lineage"]["feature_ids"]:
            assert feature_payloads[feature_id]["feature_value"]["available_at"] <= decision.decision_time.isoformat().replace("+00:00", "Z")

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "sharpe" not in summary_payload
    assert "information_ratio" not in summary_payload
    assert {benchmark.benchmark_kind for benchmark in response.benchmark_references} == {
        BenchmarkKind.FLAT_BASELINE,
        BenchmarkKind.BUY_AND_HOLD,
    }


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
