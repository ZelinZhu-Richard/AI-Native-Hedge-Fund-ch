from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.schemas import (
    AblationConfig,
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    EvaluationSlice,
    ExecutionAssumption,
    ProvenanceRecord,
    ReviewOutcome,
    ReviewTargetType,
    SignalStatus,
    StrategyFamily,
    StrategyVariant,
    StrictModel,
)
from libraries.time import Clock, FrozenClock, ensure_utc, isoformat_z
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_backtest_pipeline, run_strategy_ablation_pipeline
from pipelines.backtesting.backtest_pipeline import RunBacktestWorkflowResponse
from pipelines.backtesting.strategy_ablation_pipeline import RunStrategyAblationWorkflowResponse
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.portfolio.portfolio_review_pipeline import PortfolioReviewPipelineResponse
from pipelines.signal_generation import run_feature_signal_pipeline
from pipelines.signal_generation.feature_signal_pipeline import FeatureSignalPipelineResponse
from services.backtesting.ablation import (
    build_default_strategy_variants,
    build_strategy_specs,
    load_strategy_inputs,
)
from services.ingestion import FixtureIngestionResponse
from services.monitoring import (
    ListRecentRunSummariesRequest,
    ListRecentRunSummariesResponse,
    MonitoringService,
    RunHealthChecksRequest,
    RunHealthChecksResponse,
)
from services.operator_review import (
    AddReviewNoteRequest,
    AddReviewNoteResponse,
    ApplyReviewActionRequest,
    ApplyReviewActionResponse,
    OperatorReviewService,
    SyncReviewQueueRequest,
    SyncReviewQueueResponse,
)
from services.parsing import ExtractDocumentEvidenceResponse
from services.research_orchestrator import RunResearchWorkflowResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "ingestion"
DEFAULT_PRICE_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "backtesting" / "apex_synthetic_daily_prices.json"
)
DEFAULT_FROZEN_TIME = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


class EndToEndDemoResponse(StrictModel):
    """Convenience manifest for one reproducible end-to-end local demo run."""

    demo_run_id: str = Field(description="Stable demo run identifier.")
    company_id: str = Field(description="Covered company identifier.")
    requested_by: str = Field(description="Requester that initiated the demo.")
    frozen_time: datetime = Field(description="Deterministic UTC timestamp used by the demo.")
    base_root: Path = Field(description="Base artifact root for the isolated demo run.")
    fixtures_root: Path = Field(description="Fixture root used for ingestion.")
    price_fixture_path: Path = Field(description="Synthetic price fixture used for backtesting.")
    ingestion: list[FixtureIngestionResponse] = Field(default_factory=list)
    evidence_extraction: list[ExtractDocumentEvidenceResponse] = Field(default_factory=list)
    research: RunResearchWorkflowResponse = Field(description="Research workflow output.")
    feature_signal: FeatureSignalPipelineResponse = Field(description="Feature and signal output.")
    backtest: RunBacktestWorkflowResponse = Field(description="Single-strategy exploratory backtest.")
    ablation: RunStrategyAblationWorkflowResponse = Field(description="Baseline comparison output.")
    portfolio_review: PortfolioReviewPipelineResponse = Field(
        description="Portfolio proposal output plus any explicitly approval-gated paper-trade candidates."
    )
    review_queue: SyncReviewQueueResponse = Field(description="Review queue snapshot after demo sync.")
    review_note: AddReviewNoteResponse = Field(description="Conservative operator note recorded by the demo.")
    review_action: ApplyReviewActionResponse = Field(
        description="Conservative operator review action recorded by the demo."
    )
    health_checks: RunHealthChecksResponse = Field(
        description="Structured health checks collected after the demo run."
    )
    recent_run_summaries: ListRecentRunSummariesResponse = Field(
        description="Recent run summaries collected after the demo run."
    )
    manifest_path: Path = Field(description="Path to the persisted demo manifest JSON.")
    notes: list[str] = Field(default_factory=list)


def run_end_to_end_demo(
    *,
    fixtures_root: Path | None = None,
    price_fixture_path: Path | None = None,
    base_root: Path | None = None,
    requested_by: str = "end_to_end_demo",
    frozen_time: datetime | None = None,
) -> EndToEndDemoResponse:
    """Run the current research OS stack end to end over local fixtures."""

    resolved_time = ensure_utc(frozen_time or DEFAULT_FROZEN_TIME)
    demo_run_id = make_canonical_id(
        "demo", "release_candidate_end_to_end", isoformat_z(resolved_time)
    )
    resolved_fixtures_root = fixtures_root or DEFAULT_FIXTURES_ROOT
    resolved_price_fixture = price_fixture_path or DEFAULT_PRICE_FIXTURE_PATH
    resolved_base_root = base_root or (
        get_settings().resolved_artifact_root / "demo_runs" / demo_run_id
    )
    resolved_base_root.mkdir(parents=True, exist_ok=True)
    resolved_clock: Clock = FrozenClock(resolved_time)

    ingestion_root = resolved_base_root / "ingestion"
    parsing_root = resolved_base_root / "parsing"
    research_root = resolved_base_root / "research"
    signal_root = resolved_base_root / "signal_generation"
    backtesting_root = resolved_base_root / "backtesting"
    ablation_root = resolved_base_root / "ablation"
    experiment_root = resolved_base_root / "experiments"
    evaluation_root = resolved_base_root / "evaluation"
    portfolio_root = resolved_base_root / "portfolio"
    review_root = resolved_base_root / "review"
    audit_root = resolved_base_root / "audit"
    monitoring_root = resolved_base_root / "monitoring"

    ingestion_responses = run_fixture_ingestion_pipeline(
        fixtures_root=resolved_fixtures_root,
        output_root=ingestion_root,
        requested_by=requested_by,
        clock=resolved_clock,
    )
    evidence_responses = run_evidence_extraction_pipeline(
        ingestion_root=ingestion_root,
        output_root=parsing_root,
        requested_by=requested_by,
        clock=resolved_clock,
    )
    research_response = run_hypothesis_workflow_pipeline(
        parsing_root=parsing_root,
        ingestion_root=ingestion_root,
        output_root=research_root,
        requested_by=requested_by,
        clock=resolved_clock,
    )
    feature_signal_response = run_feature_signal_pipeline(
        research_root=research_root,
        parsing_root=parsing_root,
        output_root=signal_root,
        company_id=research_response.company_id,
        as_of_time=resolved_time,
        ablation_view=AblationView.TEXT_ONLY,
        requested_by=requested_by,
        clock=resolved_clock,
    )
    backtest_response = run_backtest_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=backtesting_root,
        company_id=research_response.company_id,
        price_fixture_path=resolved_price_fixture,
        backtest_config=_build_demo_backtest_config(now=resolved_time),
        experiment_root=experiment_root,
        requested_by=requested_by,
        clock=resolved_clock,
    )

    strategy_inputs = load_strategy_inputs(
        signal_root=signal_root,
        feature_root=signal_root,
        price_fixture_path=resolved_price_fixture,
        company_id=research_response.company_id,
        as_of_time=resolved_time,
    )
    strategy_specs = build_strategy_specs(
        families=[
            StrategyFamily.NAIVE_BASELINE,
            StrategyFamily.PRICE_ONLY_BASELINE,
            StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
            StrategyFamily.COMBINED_BASELINE,
        ],
        clock=resolved_clock,
        workflow_run_id=demo_run_id,
    )
    strategy_variants = build_default_strategy_variants(
        strategy_specs=strategy_specs,
        clock=resolved_clock,
        workflow_run_id=demo_run_id,
    )
    ablation_response = run_strategy_ablation_pipeline(
        signal_root=signal_root,
        feature_root=signal_root,
        output_root=ablation_root,
        experiment_root=experiment_root,
        evaluation_root=evaluation_root,
        price_fixture_path=resolved_price_fixture,
        company_id=strategy_inputs.company_id,
        ablation_config=_build_demo_ablation_config(
            strategy_variants=strategy_variants,
            company_id=strategy_inputs.company_id,
            price_fixture_path=resolved_price_fixture,
            now=resolved_time,
            requested_by=requested_by,
        ),
        clock=resolved_clock,
    )
    portfolio_review_response = run_portfolio_review_pipeline(
        signal_root=signal_root,
        research_root=research_root,
        ingestion_root=ingestion_root,
        backtesting_root=backtesting_root,
        output_root=portfolio_root,
        company_id=research_response.company_id,
        as_of_time=resolved_time,
        assumed_reference_prices={"APEX": 102.0},
        requested_by=requested_by,
        clock=resolved_clock,
    )

    review_service = OperatorReviewService(clock=resolved_clock)
    review_queue_response = review_service.sync_review_queue(
        SyncReviewQueueRequest(
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
        )
    )
    review_note_response = review_service.add_review_note(
        AddReviewNoteRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=portfolio_review_response.final_portfolio_proposal.portfolio_proposal_id,
            author_id="demo_operator",
            body=(
                "Demo note: this proposal remains review-bound. "
                "The demo shows the review layer, not automatic downstream promotion."
            ),
            related_artifact_ids=[
                portfolio_review_response.final_portfolio_proposal.portfolio_proposal_id,
                *[check.risk_check_id for check in portfolio_review_response.risk_checks],
            ],
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
        )
    )
    review_action_response = review_service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=portfolio_review_response.final_portfolio_proposal.portfolio_proposal_id,
            reviewer_id="demo_operator",
            outcome=ReviewOutcome.NEEDS_REVISION,
            rationale=(
                "Demo decision: keep the proposal review-bound until downstream eligibility gates are stricter."
            ),
            review_notes=[
                "The demo intentionally avoids silent approval paths.",
                "No paper-trade candidates are created until a proposal is explicitly approved.",
            ],
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
        )
    )

    monitoring_service = MonitoringService(clock=resolved_clock)
    health_checks = monitoring_service.run_health_checks(
        RunHealthChecksRequest(
            artifact_root=resolved_base_root,
            monitoring_root=monitoring_root,
            review_root=review_root,
        )
    )
    recent_run_summaries = monitoring_service.list_recent_run_summaries(
        ListRecentRunSummariesRequest(
            monitoring_root=monitoring_root,
            limit=50,
        )
    )

    manifest_path = resolved_base_root / "demo" / "manifests" / f"{demo_run_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    response = EndToEndDemoResponse(
        demo_run_id=demo_run_id,
        company_id=research_response.company_id,
        requested_by=requested_by,
        frozen_time=resolved_time,
        base_root=resolved_base_root,
        fixtures_root=resolved_fixtures_root,
        price_fixture_path=resolved_price_fixture,
        ingestion=ingestion_responses,
        evidence_extraction=evidence_responses,
        research=research_response,
        feature_signal=feature_signal_response,
        backtest=backtest_response,
        ablation=ablation_response,
        portfolio_review=portfolio_review_response,
        review_queue=review_queue_response,
        review_note=review_note_response,
        review_action=review_action_response,
        health_checks=health_checks,
        recent_run_summaries=recent_run_summaries,
        manifest_path=manifest_path,
        notes=[
            "This demo is fixture-backed, deterministic, and local only.",
            "Backtests and ablations are exploratory comparisons, not validated edge claims.",
            "The default demo stops at a review-bound portfolio proposal and does not auto-create paper-trade candidates.",
        ],
    )
    manifest_path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    return response


def main(argv: Sequence[str] | None = None) -> int:
    """Run the demo as a small CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Run the ANHF end-to-end local demo.")
    parser.add_argument("--fixtures-root", type=Path, default=DEFAULT_FIXTURES_ROOT)
    parser.add_argument("--price-fixture-path", type=Path, default=DEFAULT_PRICE_FIXTURE_PATH)
    parser.add_argument("--base-root", type=Path, default=None)
    parser.add_argument("--requested-by", default="end_to_end_demo_cli")
    parser.add_argument(
        "--frozen-time",
        default=isoformat_z(DEFAULT_FROZEN_TIME),
        help="Timezone-aware ISO-8601 timestamp, for example 2026-04-01T12:00:00Z.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    response = run_end_to_end_demo(
        fixtures_root=args.fixtures_root,
        price_fixture_path=args.price_fixture_path,
        base_root=args.base_root,
        requested_by=args.requested_by,
        frozen_time=_parse_cli_datetime(args.frozen_time),
    )
    print(f"demo_run_id={response.demo_run_id}")
    print(f"manifest_path={response.manifest_path}")
    print(f"base_root={response.base_root}")
    print(f"company_id={response.company_id}")
    return 0


def _build_demo_backtest_config(*, now: datetime) -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id(
            "btcfg",
            "release_candidate_end_to_end_demo",
            "text_only_candidate_signal",
            "2026-03-17",
            "2026-03-31",
        ),
        strategy_name="release_candidate_text_signal_exploratory",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 31),
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", "5.0", "2.0", "lag1"),
            transaction_cost_bps=5.0,
            slippage_bps=2.0,
            execution_lag_bars=1,
            decision_price_field="close",
            execution_price_field="open",
            provenance=_provenance(now=now),
            created_at=now,
            updated_at=now,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=_provenance(now=now),
        created_at=now,
        updated_at=now,
    )


def _build_demo_ablation_config(
    *,
    strategy_variants: list[StrategyVariant],
    company_id: str,
    price_fixture_path: Path,
    now: datetime,
    requested_by: str,
) -> AblationConfig:
    return AblationConfig(
        ablation_config_id=make_canonical_id("abcfg", "release_candidate_end_to_end_demo"),
        name="release_candidate_end_to_end_demo_ablation",
        strategy_variants=strategy_variants,
        evaluation_slice=EvaluationSlice(
            evaluation_slice_id=make_canonical_id(
                "eslice", "release_candidate_end_to_end_demo"
            ),
            company_id=company_id,
            test_start=date(2026, 3, 17),
            test_end=date(2026, 3, 31),
            decision_frequency="daily",
            price_fixture_path=str(price_fixture_path),
            provenance=_provenance(now=now),
            created_at=now,
            updated_at=now,
        ),
        shared_backtest_config=BacktestConfig(
            backtest_config_id=make_canonical_id(
                "btcfg", "release_candidate_end_to_end_demo", "ablation"
            ),
            strategy_name="release_candidate_shared_ablation_backtest",
            signal_family="shared_ablation_signal_family",
            ablation_view=AblationView.COMBINED,
            test_start=date(2026, 3, 17),
            test_end=date(2026, 3, 31),
            signal_status_allowlist=[SignalStatus.CANDIDATE],
            execution_assumption=ExecutionAssumption(
                execution_assumption_id=make_canonical_id("exec", "5.0", "2.0", "lag1"),
                transaction_cost_bps=5.0,
                slippage_bps=2.0,
                execution_lag_bars=1,
                decision_price_field="close",
                execution_price_field="open",
                provenance=_provenance(now=now),
                created_at=now,
                updated_at=now,
            ),
            benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
            provenance=_provenance(now=now),
            created_at=now,
            updated_at=now,
        ),
        comparison_metric_name="net_pnl",
        requested_by=requested_by,
        provenance=_provenance(now=now),
        created_at=now,
        updated_at=now,
    )


def _parse_cli_datetime(value: str) -> datetime:
    return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _provenance(*, now: datetime) -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=now)


if __name__ == "__main__":
    raise SystemExit(main())
