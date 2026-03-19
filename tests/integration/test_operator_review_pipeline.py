from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeVar, cast

from libraries.schemas import (
    AblationView,
    AuditLog,
    BacktestConfig,
    BenchmarkKind,
    DerivedArtifactValidationStatus,
    ExecutionAssumption,
    PaperTrade,
    PortfolioProposal,
    ResearchBrief,
    ReviewOutcome,
    ReviewQueueStatus,
    ReviewTargetType,
    Signal,
    SignalStatus,
    StrictModel,
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
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.signal_generation import run_feature_signal_pipeline
from services.operator_review import (
    ApplyReviewActionRequest,
    OperatorReviewService,
    SyncReviewQueueRequest,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)
TModel = TypeVar("TModel", bound=StrictModel)


def test_operator_review_pipeline_chains_research_signal_portfolio_and_trade_review(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_full_stack(artifact_root=artifact_root)
    service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))

    sync_response = service.sync_review_queue(
        SyncReviewQueueRequest(
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
        )
    )

    queue_targets = {(item.target_type, item.target_id) for item in sync_response.queue_items}
    research_brief = _load_single_model(artifact_root / "research" / "research_briefs", ResearchBrief)
    signal = _load_single_model(artifact_root / "signal_generation" / "signals", Signal)
    proposal = _load_single_model(artifact_root / "portfolio" / "portfolio_proposals", PortfolioProposal)

    assert {
        (ReviewTargetType.RESEARCH_BRIEF, research_brief.research_brief_id),
        (ReviewTargetType.SIGNAL, signal.signal_id),
        (ReviewTargetType.PORTFOLIO_PROPOSAL, proposal.portfolio_proposal_id),
    }.issubset(queue_targets)

    brief_action = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.RESEARCH_BRIEF,
            target_id=research_brief.research_brief_id,
            reviewer_id="pm_1",
            outcome=ReviewOutcome.APPROVE,
            rationale="Research support is sufficient for promotion to feature work.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    signal_action = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.SIGNAL,
            target_id=signal.signal_id,
            reviewer_id="pm_1",
            outcome=ReviewOutcome.NEEDS_REVISION,
            rationale="Signal remains review-bound until it is validated.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    proposal_action = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=proposal.portfolio_proposal_id,
            reviewer_id="risk_1",
            outcome=ReviewOutcome.NEEDS_REVISION,
            rationale="Proposal remains review-bound until a dedicated PM sign-off.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )

    assert brief_action.queue_item.queue_status is ReviewQueueStatus.RESOLVED
    assert signal_action.queue_item.queue_status is ReviewQueueStatus.AWAITING_REVISION
    assert proposal_action.queue_item.queue_status is ReviewQueueStatus.AWAITING_REVISION

    audit_logs = _load_models(artifact_root / "audit" / "audit_logs", AuditLog)
    review_action_logs = [
        log
        for log in audit_logs
        if log.event_type in {"review_action_applied", "review_escalation_requested"}
    ]
    assert review_action_logs
    assert all(log.status_before is not None and log.status_after is not None for log in review_action_logs)
    assert any(log.event_type == "review_action_applied" for log in review_action_logs)


def test_operator_review_pipeline_handles_paper_trade_after_explicit_approval(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_full_stack(artifact_root=artifact_root)

    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    signal_payload = Signal.model_validate_json(signal_path.read_text(encoding="utf-8")).model_dump(
        mode="json"
    )
    signal_payload["validation_status"] = DerivedArtifactValidationStatus.VALIDATED.value
    signal_path.write_text(json.dumps(signal_payload, indent=2), encoding="utf-8")

    run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_1",
        review_notes=["Approved for paper-trade candidate creation."],
        assumed_reference_prices={"APEX": 102.0},
        clock=FrozenClock(FIXED_NOW),
    )

    service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))
    sync_response = service.sync_review_queue(
        SyncReviewQueueRequest(
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
        )
    )
    paper_trade = _load_single_model(artifact_root / "portfolio" / "paper_trades", PaperTrade)
    assert (ReviewTargetType.PAPER_TRADE, paper_trade.paper_trade_id) in {
        (item.target_type, item.target_id) for item in sync_response.queue_items
    }

    trade_action = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PAPER_TRADE,
            target_id=paper_trade.paper_trade_id,
            reviewer_id="ops_1",
            outcome=ReviewOutcome.ESCALATE,
            rationale="Trade candidate requires escalation before approval.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )

    assert trade_action.queue_item.queue_status is ReviewQueueStatus.ESCALATED
    assert isinstance(trade_action.updated_target, PaperTrade)
    assert trade_action.updated_target.status.value == "proposed"


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
        backtest_config=_backtest_config(),
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
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _load_single_model(directory: Path, model_cls: type[TModel]) -> TModel:
    return cast(
        TModel,
        model_cls.model_validate_json(
            next(directory.glob("*.json")).read_text(encoding="utf-8")
        ),
    )


def _load_models(directory: Path, model_cls: type[TModel]) -> list[TModel]:
    return [
        cast(TModel, model_cls.model_validate_json(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.json"))
    ]
