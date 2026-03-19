from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeVar, cast

from libraries.schemas import (
    AblationConfig,
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    EvaluationSlice,
    ExecutionAssumption,
    PortfolioProposal,
    ProvenanceRecord,
    ReviewOutcome,
    ReviewTargetType,
    RunSummary,
    StrategyFamily,
    StrategyVariant,
    StrictModel,
    WorkflowStatus,
)
from libraries.time import FrozenClock
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_backtest_pipeline, run_strategy_ablation_pipeline
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
from services.monitoring import (
    GetServiceStatusesRequest,
    ListRecentFailureSummariesRequest,
    MonitoringService,
)
from services.operator_review import ApplyReviewActionRequest, OperatorReviewService

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)
TModel = TypeVar("TModel", bound=StrictModel)


def test_monitoring_pipeline_persists_run_summaries_for_target_workflows(tmp_path: Path) -> None:
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
        backtest_config=_backtest_config(),
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
        workflow_run_id="monitoring_integration_test",
    )
    strategy_variants = build_default_strategy_variants(
        strategy_specs=strategy_specs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="monitoring_integration_test",
    )
    ablation_response = run_strategy_ablation_pipeline(
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
        assumed_reference_prices={"APEX": 102.0},
        clock=FrozenClock(FIXED_NOW),
    )
    proposal = _load_single_model(
        artifact_root / "portfolio" / "portfolio_proposals",
        PortfolioProposal,
    )
    review_response = OperatorReviewService(clock=FrozenClock(FIXED_NOW)).apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=proposal.portfolio_proposal_id,
            reviewer_id="risk_1",
            outcome=ReviewOutcome.NEEDS_REVISION,
            rationale="Keep the proposal review-bound.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )

    run_summaries = _load_models(artifact_root / "monitoring" / "run_summaries", RunSummary)
    workflow_names = {summary.workflow_name for summary in run_summaries}

    assert {"fixture_ingestion", "evidence_extraction", "strategy_ablation", "review_action"}.issubset(
        workflow_names
    )

    ablation_summary = next(
        summary for summary in run_summaries if summary.workflow_name == "strategy_ablation"
    )
    assert ablation_response.ablation_result.ablation_result_id in ablation_summary.produced_artifact_ids
    assert all(
        run.backtest_run_id in ablation_summary.produced_artifact_ids
        for run in ablation_response.variant_backtest_runs
    )
    assert ablation_response.evaluation_report is not None
    assert (
        ablation_response.evaluation_report.evaluation_report_id
        in ablation_summary.produced_artifact_ids
    )

    review_summary = next(
        summary for summary in run_summaries if summary.workflow_name == "review_action"
    )
    assert review_response.review_decision.review_decision_id in review_summary.produced_artifact_ids
    assert review_response.audit_log.audit_log_id in review_summary.produced_artifact_ids

    monitoring_service = MonitoringService(clock=FrozenClock(FIXED_NOW))
    service_statuses = monitoring_service.get_service_statuses(
        GetServiceStatusesRequest(monitoring_root=artifact_root / "monitoring")
    )
    assert any(status.service_name == "backtesting" for status in service_statuses.items)
    assert any(status.service_name == "operator_review" for status in service_statuses.items)

    failure_summaries = monitoring_service.list_recent_failure_summaries(
        ListRecentFailureSummariesRequest(monitoring_root=artifact_root / "monitoring")
    )
    if any(
        summary.status in {WorkflowStatus.FAILED, WorkflowStatus.PARTIAL, WorkflowStatus.ATTENTION_REQUIRED}
        for summary in run_summaries
    ):
        assert failure_summaries.run_summaries


def _ablation_config(
    *, strategy_variants: list[StrategyVariant], company_id: str
) -> AblationConfig:
    return AblationConfig(
        ablation_config_id=make_canonical_id("abcfg", "monitoring", "integration"),
        name="day12_monitoring_ablation",
        strategy_variants=strategy_variants,
        evaluation_slice=EvaluationSlice(
            evaluation_slice_id=make_canonical_id("eslice", "monitoring", "integration"),
            company_id=company_id,
            test_start=date(2026, 3, 19),
            test_end=date(2026, 3, 31),
            decision_frequency="daily",
            price_fixture_path=str(PRICE_FIXTURE_PATH),
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        shared_backtest_config=BacktestConfig(
            backtest_config_id=make_canonical_id("btcfg", "monitoring", "integration"),
            strategy_name="day12_monitoring_shared_backtest",
            signal_family="shared_ablation_signal_family",
            ablation_view=AblationView.COMBINED,
            test_start=date(2026, 3, 19),
            test_end=date(2026, 3, 31),
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
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=_provenance(),
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


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
