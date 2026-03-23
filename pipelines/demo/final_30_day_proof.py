from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import load_local_models
from libraries.schemas import (
    AuditLog,
    DailyPaperSummary,
    OutcomeAttribution,
    PaperPositionState,
    PaperTrade,
    PositionLifecycleEvent,
    PositionLifecycleEventType,
    ReviewFollowup,
    ReviewOutcome,
    ReviewTargetType,
    RiskWarningRelevance,
    RunSummary,
    StrictModel,
    ThesisAssessment,
    TradeOutcome,
)
from libraries.time import Clock, FrozenClock, ensure_utc, isoformat_z
from libraries.utils import make_canonical_id
from pipelines.demo.end_to_end_demo import (
    DEFAULT_FIXTURES_ROOT,
    DEFAULT_FROZEN_TIME,
    DEFAULT_PRICE_FIXTURE_PATH,
    EndToEndDemoResponse,
    run_end_to_end_demo,
)
from pipelines.portfolio import run_portfolio_review_pipeline
from services.monitoring import (
    ListRecentRunSummariesRequest,
    MonitoringService,
    RunHealthChecksRequest,
)
from services.operator_review import (
    ApplyReviewActionRequest,
    ApplyReviewActionResponse,
    OperatorReviewService,
)
from services.paper_ledger import (
    GenerateDailyPaperSummaryRequest,
    PaperLedgerService,
    RecordLifecycleEventRequest,
    RecordLifecycleEventResponse,
    RecordTradeOutcomeRequest,
)


class ReviewBoundProofBranch(StrictModel):
    """Linked review-bound artifacts from the baseline end-to-end demo."""

    demo_run_id: str = Field(description="Stable review-bound demo run identifier.")
    demo_manifest_path: Path = Field(description="Path to the persisted demo manifest.")
    ingestion_document_ids: list[str] = Field(default_factory=list)
    evidence_bundle_document_ids: list[str] = Field(default_factory=list)
    hypothesis_id: str | None = Field(default=None)
    evidence_assessment_id: str = Field(description="Primary evidence-assessment identifier.")
    counter_hypothesis_id: str | None = Field(default=None)
    research_brief_id: str | None = Field(default=None)
    feature_ids: list[str] = Field(default_factory=list)
    signal_ids: list[str] = Field(default_factory=list)
    arbitration_decision_id: str | None = Field(default=None)
    backtest_run_id: str = Field(description="Exploratory backtest identifier.")
    ablation_result_id: str = Field(description="Strategy ablation result identifier.")
    portfolio_proposal_id: str = Field(description="Review-bound portfolio proposal identifier.")
    risk_summary_id: str | None = Field(default=None)
    proposal_scorecard_id: str | None = Field(default=None)
    review_queue_item_ids: list[str] = Field(default_factory=list)
    review_decision_ids: list[str] = Field(default_factory=list)
    health_check_ids: list[str] = Field(default_factory=list)
    run_summary_ids: list[str] = Field(default_factory=list)
    audit_log_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ApprovedAppendixProofBranch(StrictModel):
    """Explicit approval-only appendix proving candidate-to-ledger continuity."""

    approved_proposal_id: str = Field(description="Approved appendix proposal identifier.")
    proposal_review_decision_id: str | None = Field(default=None)
    paper_trade_id: str = Field(description="Approved appendix paper-trade identifier.")
    paper_trade_review_decision_id: str = Field(
        description="Review decision that admitted the trade into the ledger."
    )
    paper_position_state_id: str = Field(description="Admitted paper-position state identifier.")
    lifecycle_event_ids: list[str] = Field(default_factory=list)
    trade_outcome_id: str = Field(description="Recorded trade-outcome identifier.")
    outcome_attribution_id: str = Field(description="Recorded outcome-attribution identifier.")
    daily_paper_summary_id: str = Field(description="Recorded daily paper-summary identifier.")
    review_followup_ids: list[str] = Field(default_factory=list)
    run_summary_ids: list[str] = Field(default_factory=list)
    audit_log_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Final30DayProofResponse(StrictModel):
    """Compact manifest proving the first 30-day build end to end."""

    proof_run_id: str = Field(description="Stable final proof run identifier.")
    base_root: Path = Field(description="Workspace root for the final proof run.")
    frozen_time: datetime = Field(description="Deterministic UTC time used for the proof.")
    company_id: str = Field(description="Covered company identifier.")
    review_bound_branch: ReviewBoundProofBranch = Field(
        description="Baseline review-bound branch proving the default stop state."
    )
    approved_appendix: ApprovedAppendixProofBranch = Field(
        description="Explicit approval-only appendix proving paper-trade and ledger continuity."
    )
    manifest_path: Path = Field(description="Path to the persisted final proof manifest.")
    linked_run_summary_ids: list[str] = Field(default_factory=list)
    linked_review_decision_ids: list[str] = Field(default_factory=list)
    linked_audit_log_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def run_final_30_day_proof(
    *,
    fixtures_root: Path | None = None,
    price_fixture_path: Path | None = None,
    base_root: Path | None = None,
    requested_by: str = "final_30_day_proof",
    frozen_time: datetime | None = None,
) -> Final30DayProofResponse:
    """Run the release-proof path over the current local research OS stack."""

    resolved_time = ensure_utc(frozen_time or DEFAULT_FROZEN_TIME)
    proof_run_id = make_canonical_id("proof", "final_30_day", isoformat_z(resolved_time))
    resolved_fixtures_root = fixtures_root or DEFAULT_FIXTURES_ROOT
    resolved_price_fixture = price_fixture_path or DEFAULT_PRICE_FIXTURE_PATH
    resolved_base_root = base_root or (
        get_settings().resolved_artifact_root / "demo_runs" / "final_30_day_proof"
    )
    resolved_base_root.mkdir(parents=True, exist_ok=True)
    resolved_clock: Clock = FrozenClock(resolved_time)

    demo_response = run_end_to_end_demo(
        fixtures_root=resolved_fixtures_root,
        price_fixture_path=resolved_price_fixture,
        base_root=resolved_base_root,
        requested_by=requested_by,
        frozen_time=resolved_time,
    )
    review_bound_branch = _build_review_bound_branch(demo_response=demo_response)

    audit_root = resolved_base_root / "audit"
    monitoring_root = resolved_base_root / "monitoring"
    baseline_audit_log_ids = _load_ids(audit_root / "audit_logs", AuditLog, "audit_log_id")
    baseline_run_summary_ids = _load_ids(
        monitoring_root / "run_summaries", RunSummary, "run_summary_id"
    )

    approved_appendix = _run_approved_appendix_branch(
        demo_response=demo_response,
        requested_by=requested_by,
        clock=resolved_clock,
        baseline_audit_log_ids=baseline_audit_log_ids,
        baseline_run_summary_ids=baseline_run_summary_ids,
    )

    monitoring_service = MonitoringService(clock=resolved_clock)
    final_health_checks = monitoring_service.run_health_checks(
        RunHealthChecksRequest(
            artifact_root=resolved_base_root,
            monitoring_root=monitoring_root,
            review_root=resolved_base_root / "review",
        )
    )
    final_run_summaries = monitoring_service.list_recent_run_summaries(
        ListRecentRunSummariesRequest(monitoring_root=monitoring_root, limit=100)
    )
    manifest_path = resolved_base_root / "demo" / "manifests" / f"{proof_run_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    response = Final30DayProofResponse(
        proof_run_id=proof_run_id,
        base_root=resolved_base_root,
        frozen_time=resolved_time,
        company_id=demo_response.company_id,
        review_bound_branch=review_bound_branch,
        approved_appendix=approved_appendix,
        manifest_path=manifest_path,
        linked_run_summary_ids=sorted(
            {
                *review_bound_branch.run_summary_ids,
                *approved_appendix.run_summary_ids,
                *[
                    summary.run_summary_id
                    for summary in final_run_summaries.items
                ],
            }
        ),
        linked_review_decision_ids=sorted(
            {
                *review_bound_branch.review_decision_ids,
                approved_appendix.proposal_review_decision_id or "",
                approved_appendix.paper_trade_review_decision_id,
            }
            - {""}
        ),
        linked_audit_log_ids=sorted(
            {
                *review_bound_branch.audit_log_ids,
                *approved_appendix.audit_log_ids,
            }
        ),
        notes=[
            "The review-bound branch is the default truthful stop state for the current demo.",
            "The explicit approval-only appendix requires portfolio and paper-trade approvals and does not imply automatic downstream promotion.",
            "Paper-ledger lifecycle events, close, outcome, and daily summary in the appendix are manual local proof steps, not broker-connected execution.",
            f"final_health_check_count={len(final_health_checks.health_checks)}",
        ],
    )
    manifest_path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    return response


def main(argv: Sequence[str] | None = None) -> int:
    """Run the final proof wrapper as a small CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Run the ANHF final 30-day proof flow.")
    parser.add_argument("--fixtures-root", type=Path, default=DEFAULT_FIXTURES_ROOT)
    parser.add_argument("--price-fixture-path", type=Path, default=DEFAULT_PRICE_FIXTURE_PATH)
    parser.add_argument("--base-root", type=Path, default=None)
    parser.add_argument("--requested-by", default="final_30_day_proof_cli")
    parser.add_argument(
        "--frozen-time",
        default=isoformat_z(DEFAULT_FROZEN_TIME),
        help="Timezone-aware ISO-8601 timestamp, for example 2026-04-01T12:00:00Z.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    response = run_final_30_day_proof(
        fixtures_root=args.fixtures_root,
        price_fixture_path=args.price_fixture_path,
        base_root=args.base_root,
        requested_by=args.requested_by,
        frozen_time=datetime.fromisoformat(args.frozen_time.replace("Z", "+00:00")),
    )
    print(f"proof_run_id={response.proof_run_id}")
    print(f"manifest_path={response.manifest_path}")
    print(f"base_root={response.base_root}")
    print(f"company_id={response.company_id}")
    print(f"approved_paper_trade_id={response.approved_appendix.paper_trade_id}")
    return 0


def _build_review_bound_branch(*, demo_response: EndToEndDemoResponse) -> ReviewBoundProofBranch:
    ingestion_document_ids = [
        document_id
        for response in demo_response.ingestion
        for document_id in (
            response.filing.document_id if response.filing is not None else None,
            response.earnings_call.document_id if response.earnings_call is not None else None,
            response.news_item.document_id if response.news_item is not None else None,
        )
        if document_id is not None
    ]
    return ReviewBoundProofBranch(
        demo_run_id=demo_response.demo_run_id,
        demo_manifest_path=demo_response.manifest_path,
        ingestion_document_ids=ingestion_document_ids,
        evidence_bundle_document_ids=[
            bundle.document_id for bundle in demo_response.evidence_extraction
        ],
        hypothesis_id=(
            demo_response.research.hypothesis.hypothesis_id
            if demo_response.research.hypothesis is not None
            else None
        ),
        evidence_assessment_id=demo_response.research.evidence_assessment.evidence_assessment_id,
        counter_hypothesis_id=(
            demo_response.research.counter_hypothesis.counter_hypothesis_id
            if demo_response.research.counter_hypothesis is not None
            else None
        ),
        research_brief_id=(
            demo_response.research.research_brief.research_brief_id
            if demo_response.research.research_brief is not None
            else None
        ),
        feature_ids=[
            feature.feature_id for feature in demo_response.feature_signal.feature_mapping.features
        ],
        signal_ids=[
            signal.signal_id for signal in demo_response.feature_signal.signal_generation.signals
        ],
        arbitration_decision_id=(
            demo_response.feature_signal.signal_arbitration.arbitration_decision.arbitration_decision_id
            if demo_response.feature_signal.signal_arbitration.arbitration_decision is not None
            else None
        ),
        backtest_run_id=demo_response.backtest.backtest_run.backtest_run_id,
        ablation_result_id=demo_response.ablation.ablation_result.ablation_result_id,
        portfolio_proposal_id=demo_response.portfolio_review.final_portfolio_proposal.portfolio_proposal_id,
        risk_summary_id=(
            demo_response.portfolio_review.risk_summary.risk_summary_id
            if demo_response.portfolio_review.risk_summary is not None
            else None
        ),
        proposal_scorecard_id=(
            demo_response.portfolio_review.proposal_scorecard.proposal_scorecard_id
            if demo_response.portfolio_review.proposal_scorecard is not None
            else None
        ),
        review_queue_item_ids=[
            item.review_queue_item_id for item in demo_response.review_queue.queue_items
        ],
        review_decision_ids=[
            demo_response.review_action.review_decision.review_decision_id,
        ],
        health_check_ids=[
            check.health_check_id for check in demo_response.health_checks.health_checks
        ],
        run_summary_ids=[
            summary.run_summary_id for summary in demo_response.recent_run_summaries.items
        ],
        audit_log_ids=[
            demo_response.review_note.audit_log.audit_log_id,
            demo_response.review_action.audit_log.audit_log_id,
        ],
        notes=list(demo_response.notes),
    )


def _run_approved_appendix_branch(
    *,
    demo_response: EndToEndDemoResponse,
    requested_by: str,
    clock: Clock,
    baseline_audit_log_ids: set[str],
    baseline_run_summary_ids: set[str],
) -> ApprovedAppendixProofBranch:
    workspace_root = demo_response.base_root
    approved_pipeline_response = run_portfolio_review_pipeline(
        signal_root=workspace_root / "signal_generation",
        signal_arbitration_root=workspace_root / "signal_arbitration",
        research_root=workspace_root / "research",
        ingestion_root=workspace_root / "ingestion",
        backtesting_root=workspace_root / "backtesting",
        output_root=workspace_root / "portfolio",
        company_id=demo_response.company_id,
        as_of_time=demo_response.frozen_time,
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="final_proof_pm",
        review_notes=["Final proof appendix: explicit approval for paper-trade candidate creation."],
        assumed_reference_prices={"APEX": 102.0},
        requested_by=requested_by,
        clock=clock,
    )
    if not approved_pipeline_response.paper_trades:
        raise ValueError("Final proof appendix expected at least one paper trade candidate.")
    paper_trade = approved_pipeline_response.paper_trades[0]
    review_service = OperatorReviewService(clock=clock)
    trade_approval = review_service.apply_review_action(
        ApplyReviewActionRequest(
            target_type=ReviewTargetType.PAPER_TRADE,
            target_id=paper_trade.paper_trade_id,
            reviewer_id="final_proof_ops",
            outcome=ReviewOutcome.APPROVE,
            rationale="Final proof appendix: explicitly admit the paper trade into the tracked ledger.",
            portfolio_root=workspace_root / "portfolio",
            review_root=workspace_root / "review",
            audit_root=workspace_root / "audit",
            research_root=workspace_root / "research",
            signal_root=workspace_root / "signal_generation",
        )
    )
    approved_trade = trade_approval.updated_target
    assert isinstance(approved_trade, PaperTrade)
    if approved_trade.paper_position_state_id is None:
        raise ValueError("Final proof appendix expected paper-trade approval to admit the trade.")

    fill_response = _record_fill_event(
        approved_trade=approved_trade,
        review_action=trade_approval,
        output_root=workspace_root / "portfolio",
        clock=clock,
    )
    close_response = PaperLedgerService(clock=clock).record_lifecycle_event(
        RecordLifecycleEventRequest(
            paper_trade_id=approved_trade.paper_trade_id,
            paper_position_state_id=approved_trade.paper_position_state_id,
            event_type=PositionLifecycleEventType.CLOSED,
            event_time=demo_response.frozen_time.replace(hour=16),
            reference_price_usd=106.0,
            requested_by=requested_by,
        ),
        output_root=workspace_root / "portfolio",
    )
    outcome_response = PaperLedgerService(clock=clock).record_trade_outcome(
        RecordTradeOutcomeRequest(
            paper_trade_id=approved_trade.paper_trade_id,
            paper_position_state_id=approved_trade.paper_position_state_id,
            thesis_assessment=ThesisAssessment.HELD,
            risk_warning_relevance=RiskWarningRelevance.NOT_OBSERVED,
            assumption_notes=[
                "The appendix uses explicit approval and reference-price-based paper tracking."
            ],
            learning_notes=[
                "The first 30-day build proves traceable paper-ledger continuity, not execution realism."
            ],
            followup_instructions=[
                "Carry the approved paper position forward in a longer-duration phase-2 paper workflow."
            ],
            requested_by=requested_by,
        ),
        output_root=workspace_root / "portfolio",
    )
    daily_summary_response = PaperLedgerService(clock=clock).generate_daily_paper_summary(
        GenerateDailyPaperSummaryRequest(
            summary_date=date.fromisoformat(demo_response.frozen_time.date().isoformat()),
            requested_by=requested_by,
            reference_marks_by_symbol={approved_trade.symbol: 106.0},
        ),
        output_root=workspace_root / "portfolio",
    )

    audit_log_ids = sorted(
        _load_ids(workspace_root / "audit" / "audit_logs", AuditLog, "audit_log_id")
        - baseline_audit_log_ids
    )
    run_summary_ids = sorted(
        _load_ids(workspace_root / "monitoring" / "run_summaries", RunSummary, "run_summary_id")
        - baseline_run_summary_ids
    )
    outcome_attributions = load_local_models(
        workspace_root / "portfolio" / "outcome_attributions",
        OutcomeAttribution,
    )
    position_states = load_local_models(
        workspace_root / "portfolio" / "paper_position_states",
        PaperPositionState,
    )
    lifecycle_events = load_local_models(
        workspace_root / "portfolio" / "position_lifecycle_events",
        PositionLifecycleEvent,
    )
    daily_summaries = load_local_models(
        workspace_root / "portfolio" / "daily_paper_summaries",
        DailyPaperSummary,
    )
    followups = load_local_models(
        workspace_root / "portfolio" / "review_followups",
        ReviewFollowup,
    )
    trade_outcomes = load_local_models(workspace_root / "portfolio" / "trade_outcomes", TradeOutcome)
    position_state = next(
        state
        for state in position_states
        if state.paper_trade_id == approved_trade.paper_trade_id
    )
    outcome = next(
        item for item in trade_outcomes if item.paper_trade_id == approved_trade.paper_trade_id
    )
    outcome_attribution = next(
        item for item in outcome_attributions if item.trade_outcome_id == outcome.trade_outcome_id
    )
    summary = next(
        item
        for item in reversed(daily_summaries)
        if outcome.trade_outcome_id in item.trade_outcome_ids
    )
    related_lifecycle_event_ids = [
        event.position_lifecycle_event_id
        for event in lifecycle_events
        if event.paper_trade_id == approved_trade.paper_trade_id
    ]
    related_followup_ids = [
        followup.review_followup_id
        for followup in followups
        if followup.paper_trade_id == approved_trade.paper_trade_id
    ]
    return ApprovedAppendixProofBranch(
        approved_proposal_id=approved_pipeline_response.final_portfolio_proposal.portfolio_proposal_id,
        proposal_review_decision_id=(
            approved_pipeline_response.review_decision.review_decision_id
            if approved_pipeline_response.review_decision is not None
            else None
        ),
        paper_trade_id=approved_trade.paper_trade_id,
        paper_trade_review_decision_id=trade_approval.review_decision.review_decision_id,
        paper_position_state_id=position_state.paper_position_state_id,
        lifecycle_event_ids=related_lifecycle_event_ids,
        trade_outcome_id=outcome.trade_outcome_id,
        outcome_attribution_id=outcome_attribution.outcome_attribution_id,
        daily_paper_summary_id=summary.daily_paper_summary_id,
        review_followup_ids=related_followup_ids,
        run_summary_ids=run_summary_ids,
        audit_log_ids=audit_log_ids,
        notes=[
            *approved_pipeline_response.notes,
            *fill_response.notes,
            *close_response.notes,
            *outcome_response.notes,
            *daily_summary_response.notes,
            "This appendix requires explicit proposal approval and explicit paper-trade approval.",
            "This appendix does not imply automatic downstream promotion from the default review-bound demo.",
        ],
    )


def _record_fill_event(
    *,
    approved_trade: PaperTrade,
    review_action: ApplyReviewActionResponse,
    output_root: Path,
    clock: Clock,
) -> RecordLifecycleEventResponse:
    reference_price = approved_trade.assumed_reference_price_usd or 102.0
    quantity = approved_trade.quantity
    if quantity is None:
        raise ValueError("Final proof appendix expected a materialized paper-trade quantity.")
    return PaperLedgerService(clock=clock).record_lifecycle_event(
        RecordLifecycleEventRequest(
            paper_trade_id=approved_trade.paper_trade_id,
            paper_position_state_id=approved_trade.paper_position_state_id,
            event_type=PositionLifecycleEventType.SIMULATED_FILL_PLACEHOLDER,
            event_time=review_action.review_decision.decided_at,
            reference_price_usd=reference_price,
            quantity=quantity,
            requested_by="final_30_day_proof",
            related_review_decision_id=review_action.review_decision.review_decision_id,
        ),
        output_root=output_root,
    )


def _load_ids(directory: Path, model_cls: type[StrictModel], field_name: str) -> set[str]:
    return {
        getattr(model, field_name)
        for model in load_local_models(directory, model_cls)
    }
