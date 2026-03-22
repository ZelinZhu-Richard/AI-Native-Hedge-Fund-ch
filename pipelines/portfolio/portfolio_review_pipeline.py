from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import resolve_artifact_workspace, resolve_artifact_workspace_from_stage_root
from libraries.schemas import (
    ArtifactStorageLocation,
    AuditOutcome,
    PaperTrade,
    PipelineEventType,
    PortfolioAttribution,
    PortfolioConstraint,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionAttribution,
    PositionIdea,
    QualityDecision,
    ReviewDecision,
    ReviewOutcome,
    ReviewTargetType,
    RiskCheck,
    ScenarioDefinition,
    StressTestResult,
    StressTestRun,
    StrictModel,
    WorkflowStatus,
)
from libraries.time import Clock, SystemClock
from libraries.utils import (
    apply_review_decision_to_position_idea,
    make_prefixed_id,
)
from services.audit import AuditEventRequest, AuditLoggingService
from services.data_quality import DataQualityRefusalError
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.operator_review import ApplyReviewActionRequest, OperatorReviewService
from services.paper_execution import PaperExecutionService, PaperTradeProposalRequest
from services.portfolio import (
    PortfolioConstructionService,
    RunPortfolioWorkflowRequest,
    RunPortfolioWorkflowResponse,
)
from services.portfolio.storage import LocalPortfolioArtifactStore


class PortfolioReviewPipelineResponse(StrictModel):
    """End-to-end result of the Day 7 portfolio review pipeline."""

    portfolio_workflow: RunPortfolioWorkflowResponse = Field(
        description="Portfolio proposal workflow output."
    )
    final_position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Final position ideas after any optional review transition.",
    )
    final_portfolio_proposal: PortfolioProposal = Field(
        description="Final portfolio proposal after risk checks and any optional review transition."
    )
    portfolio_attribution: PortfolioAttribution | None = Field(
        default=None,
        description="Proposal-level attribution artifact when portfolio analysis has run.",
    )
    position_attributions: list[PositionAttribution] = Field(
        default_factory=list,
        description="Position-level attribution artifacts when portfolio analysis has run.",
    )
    scenario_definitions: list[ScenarioDefinition] = Field(
        default_factory=list,
        description="Scenario definitions applied during portfolio analysis.",
    )
    stress_test_run: StressTestRun | None = Field(
        default=None,
        description="Stress-test run artifact when portfolio analysis has run.",
    )
    stress_test_results: list[StressTestResult] = Field(
        default_factory=list,
        description="Structured stress-test results when portfolio analysis has run.",
    )
    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Risk checks attached to the final proposal.",
    )
    review_decision: ReviewDecision | None = Field(
        default=None,
        description="Optional portfolio-level review decision applied in the pipeline.",
    )
    paper_trades: list[PaperTrade] = Field(
        default_factory=list,
        description="Paper-trade candidates created from the final proposal.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the pipeline.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Pipeline notes describing review state and trade gating.",
    )


def run_portfolio_review_pipeline(
    *,
    signal_root: Path | None = None,
    signal_arbitration_root: Path | None = None,
    research_root: Path | None = None,
    ingestion_root: Path | None = None,
    backtesting_root: Path | None = None,
    portfolio_analysis_root: Path | None = None,
    output_root: Path | None = None,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
    constraints: list[PortfolioConstraint] | None = None,
    proposal_review_outcome: ReviewOutcome | None = None,
    reviewer_id: str | None = None,
    review_notes: list[str] | None = None,
    assumed_reference_prices: dict[str, float] | None = None,
    requested_by: str = "pipeline_portfolio_review",
    clock: Clock | None = None,
) -> PortfolioReviewPipelineResponse:
    """Run the deterministic Day 7 portfolio proposal and paper-trade review pipeline."""

    if proposal_review_outcome is not None and reviewer_id is None:
        raise ValueError("reviewer_id is required when proposal_review_outcome is supplied.")

    workspace_anchor = (
        output_root
        or signal_root
        or signal_arbitration_root
        or research_root
        or ingestion_root
        or backtesting_root
        or portfolio_analysis_root
    )
    workspace = (
        resolve_artifact_workspace_from_stage_root(workspace_anchor)
        if workspace_anchor is not None
        else resolve_artifact_workspace(workspace_root=get_settings().resolved_artifact_root)
    )
    resolved_signal_root = signal_root or workspace.signal_root
    resolved_signal_arbitration_root = signal_arbitration_root or workspace.signal_arbitration_root
    resolved_research_root = research_root or workspace.research_root
    resolved_ingestion_root = ingestion_root or workspace.ingestion_root
    resolved_backtesting_root = backtesting_root or workspace.backtesting_root
    resolved_output_root = output_root or workspace.portfolio_root
    resolved_portfolio_analysis_root = portfolio_analysis_root or workspace.portfolio_analysis_root
    audit_root = workspace.audit_root
    monitoring_root = workspace.monitoring_root
    resolved_clock = clock or SystemClock()
    resolved_review_notes = review_notes or []
    resolved_assumed_prices = assumed_reference_prices or {}
    portfolio_review_pipeline_run_id = make_prefixed_id("prpipe")
    monitoring_service = MonitoringService(clock=resolved_clock)
    started_at = resolved_clock.now()
    start_event = monitoring_service.record_pipeline_event(
        RecordPipelineEventRequest(
            workflow_name="portfolio_review_pipeline",
            workflow_run_id=portfolio_review_pipeline_run_id,
            service_name="portfolio",
            event_type=PipelineEventType.RUN_STARTED,
            status=WorkflowStatus.RUNNING,
            message="Portfolio review pipeline started.",
            related_artifact_ids=[],
            notes=[f"requested_by={requested_by}"],
        ),
        output_root=monitoring_root,
    )

    try:
        portfolio_service = PortfolioConstructionService(clock=resolved_clock)
        workflow_response = portfolio_service.run_portfolio_workflow(
            RunPortfolioWorkflowRequest(
                signal_root=resolved_signal_root,
                signal_arbitration_root=resolved_signal_arbitration_root,
                research_root=resolved_research_root,
                ingestion_root=resolved_ingestion_root,
                backtesting_root=resolved_backtesting_root,
                portfolio_analysis_root=resolved_portfolio_analysis_root,
                output_root=resolved_output_root,
                company_id=company_id,
                as_of_time=as_of_time,
                constraints=constraints or [],
                requested_by=requested_by,
            )
        )
        store = LocalPortfolioArtifactStore(root=resolved_output_root, clock=resolved_clock)
        storage_locations = list(workflow_response.storage_locations)
        notes = list(workflow_response.notes)
        final_position_ideas = list(workflow_response.position_ideas)
        final_portfolio_proposal = workflow_response.portfolio_proposal

        review_decision = None
        if proposal_review_outcome is not None:
            operator_review_response = OperatorReviewService(clock=resolved_clock).apply_review_action(
                ApplyReviewActionRequest(
                    target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
                    target_id=workflow_response.portfolio_proposal.portfolio_proposal_id,
                    reviewer_id=reviewer_id or "missing_reviewer",
                    outcome=proposal_review_outcome,
                    rationale=(
                        resolved_review_notes[0]
                        if resolved_review_notes
                        else f"Portfolio review outcome recorded as `{proposal_review_outcome.value}`."
                    ),
                    blocking_issues=(
                        []
                        if proposal_review_outcome is ReviewOutcome.APPROVE
                        else workflow_response.portfolio_proposal.blocking_issues
                    ),
                    conditions=[],
                    review_notes=resolved_review_notes,
                    portfolio_root=resolved_output_root,
                    review_root=workspace.review_root,
                    audit_root=audit_root,
                )
            )
            review_decision = operator_review_response.review_decision
            storage_locations.extend(operator_review_response.storage_locations)
            final_position_ideas = [
                apply_review_decision_to_position_idea(
                    position_idea=position_idea,
                    review_decision=review_decision,
                )
                for position_idea in workflow_response.position_ideas
            ]
            updated_proposal = operator_review_response.updated_target
            assert isinstance(updated_proposal, PortfolioProposal)
            final_portfolio_proposal = updated_proposal.model_copy(
                update={"position_ideas": final_position_ideas}
            )
            for position_idea in final_position_ideas:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=position_idea.position_idea_id,
                        category="position_ideas",
                        model=position_idea,
                        source_reference_ids=position_idea.provenance.source_reference_ids,
                    )
                )
            storage_locations.append(
                store.persist_model(
                    artifact_id=final_portfolio_proposal.portfolio_proposal_id,
                    category="portfolio_proposals",
                    model=final_portfolio_proposal,
                    source_reference_ids=final_portfolio_proposal.provenance.source_reference_ids,
                )
            )
            notes.append(f"proposal_review_outcome={proposal_review_outcome.value}")

        paper_execution_service = PaperExecutionService(clock=resolved_clock)
        paper_trade_response = paper_execution_service.propose_trades(
            PaperTradeProposalRequest(
                portfolio_proposal=final_portfolio_proposal,
                assumed_reference_prices=resolved_assumed_prices,
                requested_by=requested_by,
            ),
            output_root=workspace.data_quality_root,
        )
        storage_locations.extend(paper_trade_response.storage_locations)
        notes.extend(paper_trade_response.notes)
        if paper_trade_response.validation_gate is not None:
            notes.append(
                f"paper_trade_validation_gate_id={paper_trade_response.validation_gate.validation_gate_id}"
            )
            notes.append(
                f"paper_trade_quality_decision={paper_trade_response.validation_gate.decision.value}"
            )
            if paper_trade_response.validation_gate.refusal_reason is not None:
                notes.append(
                    "paper_trade_refusal_reason="
                    f"{paper_trade_response.validation_gate.refusal_reason.value}"
                )
        proposal_is_approved = final_portfolio_proposal.status is PortfolioProposalStatus.APPROVED
        if not proposal_is_approved and not paper_trade_response.proposed_trades:
            notes.append(
                "Paper-trade creation stopped at the review gate because the portfolio proposal is not approved."
            )
        for paper_trade in paper_trade_response.proposed_trades:
            storage_locations.append(
                store.persist_model(
                    artifact_id=paper_trade.paper_trade_id,
                    category="paper_trades",
                    model=paper_trade,
                    source_reference_ids=paper_trade.provenance.source_reference_ids,
                )
            )
        audit_service = AuditLoggingService(clock=resolved_clock)
        if paper_trade_response.proposed_trades:
            audit_response = audit_service.record_event(
                AuditEventRequest(
                    event_type="paper_trade_candidates_created",
                    actor_type="service",
                    actor_id="paper_execution",
                    target_type="portfolio_proposal",
                    target_id=final_portfolio_proposal.portfolio_proposal_id,
                    action="created",
                    outcome=AuditOutcome.SUCCESS,
                    reason="Paper-trade candidates were created from a review-ready portfolio proposal.",
                    request_id=workflow_response.portfolio_workflow_id,
                    related_artifact_ids=[
                        *[trade.paper_trade_id for trade in paper_trade_response.proposed_trades],
                        final_portfolio_proposal.portfolio_proposal_id,
                        *(
                            [paper_trade_response.validation_gate.validation_gate_id]
                            if paper_trade_response.validation_gate is not None
                            else []
                        ),
                    ],
                    notes=paper_trade_response.notes,
                ),
                output_root=audit_root,
            )
            storage_locations.append(audit_response.storage_location)
        pipeline_audit_response = audit_service.record_event(
            AuditEventRequest(
                event_type=(
                    "portfolio_review_pipeline_completed"
                    if not final_portfolio_proposal.blocking_issues
                    else "portfolio_review_pipeline_blocked"
                ),
                actor_type="service",
                actor_id="portfolio_review_pipeline",
                target_type="portfolio_workflow",
                target_id=workflow_response.portfolio_workflow_id,
                action="completed" if not final_portfolio_proposal.blocking_issues else "blocked",
                outcome=(
                    AuditOutcome.SUCCESS
                    if not final_portfolio_proposal.blocking_issues
                    else AuditOutcome.WARNING
                ),
                reason=(
                    "Portfolio review pipeline completed without blocking risk issues."
                    if not final_portfolio_proposal.blocking_issues
                    else "Portfolio review pipeline completed with blocking risk issues."
                ),
                request_id=workflow_response.portfolio_workflow_id,
                related_artifact_ids=[
                    final_portfolio_proposal.portfolio_proposal_id,
                    *[idea.position_idea_id for idea in final_position_ideas],
                    *[check.risk_check_id for check in final_portfolio_proposal.risk_checks],
                    *([review_decision.review_decision_id] if review_decision is not None else []),
                    *[trade.paper_trade_id for trade in paper_trade_response.proposed_trades],
                    *(
                        [paper_trade_response.validation_gate.validation_gate_id]
                        if paper_trade_response.validation_gate is not None
                        else []
                    ),
                ],
                notes=notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(pipeline_audit_response.storage_location)
        completed_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="portfolio_review_pipeline",
                workflow_run_id=portfolio_review_pipeline_run_id,
                service_name="portfolio",
                event_type=PipelineEventType.RUN_COMPLETED,
                status=WorkflowStatus.SUCCEEDED,
                message="Portfolio review pipeline completed.",
                related_artifact_ids=[
                    final_portfolio_proposal.portfolio_proposal_id,
                    *[idea.position_idea_id for idea in final_position_ideas],
                    *[check.risk_check_id for check in final_portfolio_proposal.risk_checks],
                    *[trade.paper_trade_id for trade in paper_trade_response.proposed_trades],
                    *(
                        [paper_trade_response.validation_gate.validation_gate_id]
                        if paper_trade_response.validation_gate is not None
                        else []
                    ),
                ],
                notes=[f"requested_by={requested_by}"],
            ),
            output_root=monitoring_root,
        )
        pipeline_event_ids = [
            start_event.pipeline_event.pipeline_event_id,
            completed_event.pipeline_event.pipeline_event_id,
        ]
        summary_status = WorkflowStatus.SUCCEEDED
        attention_reasons: list[str] = []
        paper_trade_blocked = (
            paper_trade_response.quality_decision
            in {QualityDecision.REFUSE, QualityDecision.QUARANTINE}
            if paper_trade_response.quality_decision is not None
            else False
        )
        requires_attention = bool(final_portfolio_proposal.blocking_issues) or (
            not paper_trade_response.proposed_trades
        )
        if requires_attention:
            attention_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="portfolio_review_pipeline",
                    workflow_run_id=portfolio_review_pipeline_run_id,
                    service_name="portfolio",
                    event_type=PipelineEventType.ATTENTION_REQUIRED,
                    status=WorkflowStatus.ATTENTION_REQUIRED,
                    message=(
                        final_portfolio_proposal.blocking_issues[0]
                        if final_portfolio_proposal.blocking_issues
                        else paper_trade_response.notes[0]
                        if paper_trade_response.notes
                        else "Approved portfolio proposal produced no paper-trade candidates."
                    ),
                    related_artifact_ids=[
                        final_portfolio_proposal.portfolio_proposal_id,
                        *(
                            [paper_trade_response.validation_gate.validation_gate_id]
                            if paper_trade_response.validation_gate is not None
                            else []
                        ),
                    ],
                    notes=[f"requested_by={requested_by}"],
                ),
                output_root=monitoring_root,
            )
            pipeline_event_ids.append(attention_event.pipeline_event.pipeline_event_id)
            summary_status = WorkflowStatus.ATTENTION_REQUIRED
            attention_reasons.extend(final_portfolio_proposal.blocking_issues)
            if not proposal_is_approved and not paper_trade_response.proposed_trades:
                attention_reasons.append("proposal_not_approved_for_paper_trade")
            if paper_trade_blocked:
                attention_reasons.append("paper_trade_quality_refusal")
            if proposal_is_approved and not paper_trade_response.proposed_trades:
                attention_reasons.append("no_paper_trade_candidates")
        monitoring_service.record_run_summary(
            RecordRunSummaryRequest(
                workflow_name="portfolio_review_pipeline",
                workflow_run_id=portfolio_review_pipeline_run_id,
                service_name="portfolio",
                requested_by=requested_by,
                status=summary_status,
                started_at=started_at,
                completed_at=resolved_clock.now(),
                storage_locations=storage_locations,
                produced_artifact_ids=[
                    workflow_response.portfolio_workflow_id,
                    final_portfolio_proposal.portfolio_proposal_id,
                    *[idea.position_idea_id for idea in final_position_ideas],
                    *[check.risk_check_id for check in final_portfolio_proposal.risk_checks],
                    *([review_decision.review_decision_id] if review_decision is not None else []),
                    *[trade.paper_trade_id for trade in paper_trade_response.proposed_trades],
                    *(
                        [paper_trade_response.validation_gate.validation_gate_id]
                        if paper_trade_response.validation_gate is not None
                        else []
                    ),
                ],
                pipeline_event_ids=pipeline_event_ids,
                attention_reasons=attention_reasons,
                notes=notes,
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        return PortfolioReviewPipelineResponse(
            portfolio_workflow=workflow_response,
            final_position_ideas=final_position_ideas,
            final_portfolio_proposal=final_portfolio_proposal,
            portfolio_attribution=workflow_response.portfolio_attribution,
            position_attributions=workflow_response.position_attributions,
            scenario_definitions=workflow_response.scenario_definitions,
            stress_test_run=workflow_response.stress_test_run,
            stress_test_results=workflow_response.stress_test_results,
            risk_checks=final_portfolio_proposal.risk_checks,
            review_decision=review_decision,
            paper_trades=paper_trade_response.proposed_trades,
            storage_locations=storage_locations,
            notes=notes,
        )
    except DataQualityRefusalError as exc:
        failed_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="portfolio_review_pipeline",
                workflow_run_id=portfolio_review_pipeline_run_id,
                service_name="portfolio",
                event_type=PipelineEventType.RUN_FAILED,
                status=WorkflowStatus.FAILED,
                message=f"Portfolio review pipeline failed quality validation: {exc}",
                related_artifact_ids=[exc.result.validation_gate.validation_gate_id],
                notes=[
                    f"requested_by={requested_by}",
                    f"quality_decision={exc.result.validation_gate.decision.value}",
                    (
                        "refusal_reason="
                        f"{exc.result.validation_gate.refusal_reason.value}"
                        if exc.result.validation_gate.refusal_reason is not None
                        else "refusal_reason=none"
                    ),
                ],
            ),
            output_root=monitoring_root,
        )
        monitoring_service.record_run_summary(
            RecordRunSummaryRequest(
                workflow_name="portfolio_review_pipeline",
                workflow_run_id=portfolio_review_pipeline_run_id,
                service_name="portfolio",
                requested_by=requested_by,
                status=WorkflowStatus.FAILED,
                started_at=started_at,
                completed_at=resolved_clock.now(),
                storage_locations=exc.storage_locations,
                pipeline_event_ids=[
                    start_event.pipeline_event.pipeline_event_id,
                    failed_event.pipeline_event.pipeline_event_id,
                ],
                failure_messages=[str(exc)],
                notes=[
                    f"requested_by={requested_by}",
                    f"validation_gate_id={exc.result.validation_gate.validation_gate_id}",
                    f"quality_decision={exc.result.validation_gate.decision.value}",
                    (
                        "refusal_reason="
                        f"{exc.result.validation_gate.refusal_reason.value}"
                        if exc.result.validation_gate.refusal_reason is not None
                        else "refusal_reason=none"
                    ),
                ],
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        raise
    except Exception as exc:
        failed_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="portfolio_review_pipeline",
                workflow_run_id=portfolio_review_pipeline_run_id,
                service_name="portfolio",
                event_type=PipelineEventType.RUN_FAILED,
                status=WorkflowStatus.FAILED,
                message=f"Portfolio review pipeline failed: {exc}",
                related_artifact_ids=[],
                notes=[f"requested_by={requested_by}"],
            ),
            output_root=monitoring_root,
        )
        monitoring_service.record_run_summary(
            RecordRunSummaryRequest(
                workflow_name="portfolio_review_pipeline",
                workflow_run_id=portfolio_review_pipeline_run_id,
                service_name="portfolio",
                requested_by=requested_by,
                status=WorkflowStatus.FAILED,
                started_at=started_at,
                completed_at=resolved_clock.now(),
                storage_locations=[],
                pipeline_event_ids=[
                    start_event.pipeline_event.pipeline_event_id,
                    failed_event.pipeline_event.pipeline_event_id,
                ],
                failure_messages=[str(exc)],
                notes=[f"requested_by={requested_by}"],
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        raise
