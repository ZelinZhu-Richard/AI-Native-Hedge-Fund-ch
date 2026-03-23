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
    AddReviewNoteRequest,
    ApplyReviewActionRequest,
    AssignReviewRequest,
    GetReviewContextRequest,
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


def test_operator_review_workflow_syncs_queue_and_records_actions(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
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

    target_types = {item.target_type for item in sync_response.queue_items}
    assert {
        ReviewTargetType.RESEARCH_BRIEF,
        ReviewTargetType.SIGNAL,
        ReviewTargetType.PORTFOLIO_PROPOSAL,
    }.issubset(target_types)
    signal_queue_item = next(
        item for item in sync_response.queue_items if item.target_type is ReviewTargetType.SIGNAL
    )
    assert signal_queue_item.action_recommendation.recommended_outcome is ReviewOutcome.NEEDS_REVISION

    research_brief = _load_single_model(artifact_root / "research" / "research_briefs", ResearchBrief)
    signal = _load_single_model(artifact_root / "signal_generation" / "signals", Signal)
    proposal = _load_single_model(
        artifact_root / "portfolio" / "portfolio_proposals",
        PortfolioProposal,
    )
    proposal_context = service.get_review_context(
        GetReviewContextRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=proposal.portfolio_proposal_id,
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert proposal_context.portfolio_attribution is not None
    assert proposal_context.position_attributions
    assert proposal_context.stress_test_run is not None
    assert proposal_context.stress_test_results
    assert proposal_context.strategy_to_paper_mapping is not None
    assert proposal_context.reconciliation_report is not None
    assert proposal_context.realism_warnings

    note_response = service.add_review_note(
        AddReviewNoteRequest(
            target_type=ReviewTargetType.RESEARCH_BRIEF,
            target_id=research_brief.research_brief_id,
            author_id="analyst_1",
            body="Needs an explicit note about remaining demand uncertainty.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert note_response.queue_item.review_note_ids == [note_response.review_note.review_note_id]

    assignment_response = service.assign_review(
        AssignReviewRequest(
            target_type=ReviewTargetType.SIGNAL,
            target_id=signal.signal_id,
            assigned_by="lead_reviewer",
            assignee_id="pm_1",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert assignment_response.queue_item.review_assignment_id == assignment_response.review_assignment.review_assignment_id
    assert assignment_response.queue_item.queue_status is ReviewQueueStatus.IN_REVIEW

    approved_brief = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.RESEARCH_BRIEF,
            target_id=research_brief.research_brief_id,
            reviewer_id="pm_1",
            outcome=ReviewOutcome.APPROVE,
            rationale="Support quality is sufficient for feature work.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert isinstance(approved_brief.updated_target, ResearchBrief)
    assert approved_brief.updated_target.review_status.value == "approved_for_feature_work"
    assert approved_brief.audit_log.status_before == "pending_human_review"
    assert approved_brief.audit_log.status_after == "approved_for_feature_work"

    revised_signal = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.SIGNAL,
            target_id=signal.signal_id,
            reviewer_id="pm_1",
            outcome=ReviewOutcome.NEEDS_REVISION,
            rationale="Signal remains unvalidated and should stay review-bound.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert isinstance(revised_signal.updated_target, Signal)
    assert revised_signal.updated_target.status is SignalStatus.CANDIDATE

    rejected_proposal = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=proposal.portfolio_proposal_id,
            reviewer_id="risk_1",
            outcome=ReviewOutcome.REJECT,
            rationale="Proposal is not ready for approval in this test path.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert isinstance(rejected_proposal.updated_target, PortfolioProposal)
    assert rejected_proposal.updated_target.status.value == "rejected"
    assert rejected_proposal.queue_item.queue_status is ReviewQueueStatus.RESOLVED

    context = service.get_review_context(
        GetReviewContextRequest(
            target_type=ReviewTargetType.RESEARCH_BRIEF,
            target_id=research_brief.research_brief_id,
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert context.research_brief is not None
    assert context.hypothesis is not None
    assert context.evidence_assessment is not None
    assert context.supporting_evidence_links
    assert context.review_notes
    assert context.review_decisions

    audit_logs = _load_models(artifact_root / "audit" / "audit_logs", AuditLog)
    assert any(log.status_before and log.status_after for log in audit_logs)


def test_operator_review_blocks_unvalidated_signal_approval(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))
    signal = _load_single_model(artifact_root / "signal_generation" / "signals", Signal)

    try:
        service.apply_review_action(
            ApplyReviewActionRequest(
                target_type=ReviewTargetType.SIGNAL,
                target_id=signal.signal_id,
                reviewer_id="pm_1",
                outcome=ReviewOutcome.APPROVE,
                rationale="This should fail because the signal is still unvalidated.",
                review_root=artifact_root / "review",
                audit_root=artifact_root / "audit",
                research_root=artifact_root / "research",
                signal_root=artifact_root / "signal_generation",
                portfolio_root=artifact_root / "portfolio",
            )
        )
    except ValueError as exc:
        assert "validated status" in str(exc)
    else:
        raise AssertionError("Expected unvalidated signal approval to be blocked.")


def test_operator_review_infers_workspace_from_review_root_for_context(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))
    proposal = _load_single_model(
        artifact_root / "portfolio" / "portfolio_proposals",
        PortfolioProposal,
    )

    context = service.get_review_context(
        GetReviewContextRequest(
            target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
            target_id=proposal.portfolio_proposal_id,
            review_root=artifact_root / "review",
        )
    )

    assert context.portfolio_proposal is not None
    assert context.portfolio_attribution is not None
    assert context.stress_test_results


def test_operator_review_rejects_mismatched_explicit_workspace_roots(tmp_path: Path) -> None:
    service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))

    try:
        service.sync_review_queue(
            SyncReviewQueueRequest(
                research_root=tmp_path / "workspace_one" / "research",
                review_root=tmp_path / "workspace_two" / "review",
            )
        )
    except ValueError as exc:
        assert "same artifact workspace" in str(exc)
    else:
        raise AssertionError("Expected mismatched explicit review roots to be rejected.")


def test_operator_review_allows_validated_signal_approval_and_paper_trade_escalation(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_full_stack(artifact_root=artifact_root)

    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    signal_payload = json.loads(signal_path.read_text(encoding="utf-8"))
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
    signal = _load_single_model(artifact_root / "signal_generation" / "signals", Signal)
    paper_trade_payload = json.loads(
        next((artifact_root / "portfolio" / "paper_trades").glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    paper_trade_id = paper_trade_payload["paper_trade_id"]

    approved_signal = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.SIGNAL,
            target_id=signal.signal_id,
            reviewer_id="pm_1",
            outcome=ReviewOutcome.APPROVE,
            rationale="Signal is validated and reviewable.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert isinstance(approved_signal.updated_target, Signal)
    assert approved_signal.updated_target.status is SignalStatus.APPROVED

    escalated_trade = service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PAPER_TRADE,
            target_id=paper_trade_id,
            reviewer_id="ops_1",
            outcome=ReviewOutcome.ESCALATE,
            rationale="Paper trade requires escalation before approval.",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
        )
    )
    assert isinstance(escalated_trade.updated_target, PaperTrade)
    assert escalated_trade.updated_target.status.value == "proposed"
    assert escalated_trade.queue_item.queue_status is ReviewQueueStatus.ESCALATED
    assert escalated_trade.audit_log.action == "escalate"


def test_operator_review_recommendation_respects_blocking_proposals(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    proposal_path = next((artifact_root / "portfolio" / "portfolio_proposals").glob("*.json"))
    payload = json.loads(proposal_path.read_text(encoding="utf-8"))
    payload["blocking_issues"] = ["gross exposure exceeds hard limit"]
    proposal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    service = OperatorReviewService(clock=FrozenClock(FIXED_NOW))
    response = service.sync_review_queue(
        SyncReviewQueueRequest(
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
        )
    )

    proposal_item = next(
        item for item in response.queue_items if item.target_type is ReviewTargetType.PORTFOLIO_PROPOSAL
    )
    assert proposal_item.action_recommendation.recommended_outcome is ReviewOutcome.NEEDS_REVISION
    assert proposal_item.action_recommendation.blocking_reasons


def _build_full_stack(*, artifact_root: Path) -> Path:
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
    return artifact_root


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
