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
    ReviewOutcome,
    RunSummary,
    SignalStatus,
    StrategyFamily,
    StrategyVariant,
    WorkflowStatus,
)
from libraries.time import FrozenClock
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_strategy_ablation_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.signal_generation import run_feature_signal_pipeline
from services.backtesting.ablation import (
    build_default_strategy_variants,
    build_strategy_specs,
    load_strategy_inputs,
)
from services.red_team import RedTeamService, RunRedTeamSuiteRequest

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 19, 16, 0, tzinfo=UTC)


def test_red_team_suite_records_failures_without_mutating_upstream_artifacts(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_stack(artifact_root=artifact_root)

    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    proposal_path = next((artifact_root / "portfolio" / "portfolio_proposals").glob("*.json"))
    experiment_path = next((artifact_root / "experiments" / "experiments").glob("*.json"))
    signal_before = signal_path.read_text(encoding="utf-8")
    proposal_before = proposal_path.read_text(encoding="utf-8")
    experiment_before = experiment_path.read_text(encoding="utf-8")

    response = RedTeamService(clock=FrozenClock(FIXED_NOW)).run_red_team_suite(
        RunRedTeamSuiteRequest(
            parsing_root=artifact_root / "parsing",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            review_root=artifact_root / "review",
            evaluation_root=artifact_root / "evaluation",
            experiment_root=artifact_root / "experiments",
            output_root=artifact_root / "red_team",
            monitoring_root=artifact_root / "monitoring",
            audit_root=artifact_root / "audit",
            requested_by="integration_test",
        )
    )

    assert {case.scenario_name for case in response.red_team_cases} == {
        "missing_provenance",
        "contradictory_evidence",
        "timestamp_corruption",
        "incomplete_review_state",
        "unsupported_causal_claim",
        "malformed_portfolio_inputs",
        "weak_signal_lineage",
        "empty_extraction_downstream",
        "paper_trade_missing_approval_state",
        "evaluation_missing_references",
    }
    assert response.run_summary is not None
    assert response.run_summary.status is WorkflowStatus.FAILED
    assert response.alert_records
    assert (artifact_root / "red_team" / "cases").exists()
    assert (artifact_root / "red_team" / "guardrail_violations").exists()
    assert (artifact_root / "red_team" / "safety_findings").exists()

    monitoring_summaries = _load_run_summaries(artifact_root / "monitoring" / "run_summaries")
    assert any(summary.workflow_name == "red_team_suite" for summary in monitoring_summaries)
    assert signal_path.read_text(encoding="utf-8") == signal_before
    assert proposal_path.read_text(encoding="utf-8") == proposal_before
    assert experiment_path.read_text(encoding="utf-8") == experiment_before


def _build_stack(*, artifact_root: Path) -> None:
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
        workflow_run_id="red_team_integration",
    )
    strategy_variants = build_default_strategy_variants(
        strategy_specs=strategy_specs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="red_team_integration",
    )
    run_strategy_ablation_pipeline(
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
    run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_1",
        review_notes=["Proposal approved for paper-trade review."],
        assumed_reference_prices={"APEX": 102.0},
        clock=FrozenClock(FIXED_NOW),
    )


def _ablation_config(
    *, strategy_variants: list[StrategyVariant], company_id: str
) -> AblationConfig:
    return AblationConfig(
        ablation_config_id=make_canonical_id("abcfg", "red_team", "integration"),
        name="red_team_strategy_ablation",
        strategy_variants=strategy_variants,
        evaluation_slice=EvaluationSlice(
            evaluation_slice_id=make_canonical_id("eslice", "red_team", "integration"),
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
            backtest_config_id=make_canonical_id("btcfg", "red_team", "integration"),
            strategy_name="red_team_shared_backtest",
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


def _load_run_summaries(directory: Path) -> list[RunSummary]:
    return [
        RunSummary.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
