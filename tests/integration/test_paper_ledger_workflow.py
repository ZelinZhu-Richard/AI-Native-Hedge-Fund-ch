from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from libraries.core import load_local_models
from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    DailyPaperSummary,
    ExecutionAssumption,
    OutcomeAttribution,
    PaperPositionState,
    PaperTrade,
    PositionLifecycleEventType,
    ReviewOutcome,
    ReviewTargetType,
    RiskWarningRelevance,
    SignalStatus,
    ThesisAssessment,
    TradeOutcome,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.time import FrozenClock
from pipelines.backtesting import run_backtest_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.signal_generation import run_feature_signal_pipeline
from services.operator_review import (
    ApplyReviewActionRequest,
    GetReviewContextRequest,
    OperatorReviewService,
)
from services.paper_ledger import (
    GenerateDailyPaperSummaryRequest,
    PaperLedgerService,
    RecordLifecycleEventRequest,
    RecordTradeOutcomeRequest,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_paper_trade_approval_creates_position_state_and_followup_when_materialization_is_missing(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_full_stack(artifact_root=artifact_root)
    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_test",
        review_notes=["Approved for paper-trade candidate creation."],
        clock=FrozenClock(FIXED_NOW),
    )

    paper_trade = response.paper_trades[0]
    review_service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))
    approval = review_service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PAPER_TRADE,
            target_id=paper_trade.paper_trade_id,
            reviewer_id="ops_test",
            outcome=ReviewOutcome.APPROVE,
            rationale="Admit the paper trade into the tracked ledger.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )

    approved_trade = approval.updated_target
    assert isinstance(approved_trade, PaperTrade)
    assert approved_trade.paper_position_state_id is not None
    states = load_local_models(artifact_root / "portfolio" / "paper_position_states", PaperPositionState)
    assert len(states) == 1
    followup_paths = sorted((artifact_root / "portfolio" / "review_followups").glob("*.json"))
    assert followup_paths
    assert states[0].state.value == "approved_pending_fill"


def test_paper_ledger_tracks_lifecycle_outcome_and_daily_summary_back_to_review_context(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_full_stack(artifact_root=artifact_root)
    pipeline_response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_test",
        review_notes=["Approved for paper-trade candidate creation."],
        assumed_reference_prices={"APEX": 102.0},
        clock=FrozenClock(FIXED_NOW),
    )
    paper_trade = pipeline_response.paper_trades[0]
    review_service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))
    approval = review_service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PAPER_TRADE,
            target_id=paper_trade.paper_trade_id,
            reviewer_id="ops_test",
            outcome=ReviewOutcome.APPROVE,
            rationale="Approve paper trade for tracked outcome workflow.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    approved_trade = approval.updated_target
    assert isinstance(approved_trade, PaperTrade)
    assert approved_trade.paper_position_state_id is not None

    ledger_service = PaperLedgerService(clock=FrozenClock(FIXED_NOW))
    fill_response = ledger_service.record_lifecycle_event(
        RecordLifecycleEventRequest(
            paper_trade_id=approved_trade.paper_trade_id,
            paper_position_state_id=approved_trade.paper_position_state_id,
            event_type=PositionLifecycleEventType.SIMULATED_FILL_PLACEHOLDER,
            event_time=FIXED_NOW,
            reference_price_usd=102.0,
            quantity=approved_trade.quantity,
            requested_by="ops_test",
        ),
        output_root=artifact_root / "portfolio",
    )
    assert fill_response.updated_paper_trade.status.value == "simulated"
    assert fill_response.updated_paper_position_state.state.value == "open"

    close_response = ledger_service.record_lifecycle_event(
        RecordLifecycleEventRequest(
            paper_trade_id=approved_trade.paper_trade_id,
            paper_position_state_id=approved_trade.paper_position_state_id,
            event_type=PositionLifecycleEventType.CLOSED,
            event_time=FIXED_NOW.replace(hour=16),
            reference_price_usd=106.0,
            requested_by="ops_test",
        ),
        output_root=artifact_root / "portfolio",
    )
    assert close_response.updated_paper_position_state.state.value == "closed"
    assert close_response.updated_paper_position_state.latest_pnl_placeholder is not None

    outcome_response = ledger_service.record_trade_outcome(
        RecordTradeOutcomeRequest(
            paper_trade_id=approved_trade.paper_trade_id,
            paper_position_state_id=approved_trade.paper_position_state_id,
            thesis_assessment=ThesisAssessment.HELD,
            risk_warning_relevance=RiskWarningRelevance.NOT_OBSERVED,
            assumption_notes=["Reference-price-only tracking."],
            learning_notes=["Keep the same-company review path concise."],
            followup_instructions=["Review whether the horizon should be shortened next time."],
            requested_by="ops_test",
        ),
        output_root=artifact_root / "portfolio",
    )
    assert outcome_response.trade_outcome.thesis_assessment is ThesisAssessment.HELD
    assert outcome_response.review_followups

    summary_response = ledger_service.generate_daily_paper_summary(
        GenerateDailyPaperSummaryRequest(
            summary_date=date(2026, 3, 22),
            requested_by="ops_test",
            reference_marks_by_symbol={"APEX": 106.0},
        ),
        output_root=artifact_root / "portfolio",
    )
    assert summary_response.daily_paper_summary.trade_outcome_ids == [
        outcome_response.trade_outcome.trade_outcome_id
    ]
    assert summary_response.daily_paper_summary.open_review_followup_ids

    trade_context = review_service.get_review_context(
        GetReviewContextRequest(
            target_type=ReviewTargetType.PAPER_TRADE,
            target_id=approved_trade.paper_trade_id,
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    proposal_context = review_service.get_review_context(
        GetReviewContextRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=pipeline_response.final_portfolio_proposal.portfolio_proposal_id,
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )

    assert trade_context.paper_position_states
    assert trade_context.paper_ledger_entries
    assert trade_context.position_lifecycle_events
    assert trade_context.trade_outcomes
    assert trade_context.outcome_attributions
    assert trade_context.review_followups
    assert trade_context.daily_paper_summaries
    assert proposal_context.paper_position_states
    assert proposal_context.trade_outcomes
    assert proposal_context.outcome_attributions
    assert proposal_context.daily_paper_summaries

    attributions = load_local_models(
        artifact_root / "portfolio" / "outcome_attributions",
        OutcomeAttribution,
    )
    summaries = load_local_models(
        artifact_root / "portfolio" / "daily_paper_summaries",
        DailyPaperSummary,
    )
    outcomes = load_local_models(artifact_root / "portfolio" / "trade_outcomes", TradeOutcome)
    assert attributions[0].signal_id == pipeline_response.final_position_ideas[0].signal_id
    assert outcomes[0].trade_outcome_id == outcome_response.trade_outcome.trade_outcome_id
    assert summaries[-1].daily_paper_summary_id == summary_response.daily_paper_summary.daily_paper_summary_id


def _build_full_stack(*, artifact_root: Path) -> None:
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
        backtest_config=BacktestConfig(
            backtest_config_id="btcfg_day26",
            strategy_name="day26_paper_ledger_test",
            signal_family="text_only_candidate_signal",
            ablation_view=AblationView.TEXT_ONLY,
            test_start=date(2026, 3, 17),
            test_end=date(2026, 3, 30),
            signal_status_allowlist=[SignalStatus.CANDIDATE],
            execution_assumption=ExecutionAssumption(
                execution_assumption_id="exec_day26",
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
        clock=FrozenClock(FIXED_NOW),
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
