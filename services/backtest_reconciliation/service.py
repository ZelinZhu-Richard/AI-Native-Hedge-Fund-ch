from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.core import (
    ArtifactWorkspace,
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    AssumptionMismatch,
    AvailabilityMismatch,
    BacktestRun,
    CostModel,
    ExecutionAssumption,
    ExecutionTimingRule,
    ExperimentArtifact,
    ExperimentArtifactRole,
    FillAssumption,
    PaperTrade,
    PipelineEventType,
    PortfolioProposal,
    RealismWarning,
    ReconciliationReport,
    Severity,
    Signal,
    StrategyToPaperMapping,
    StrictModel,
    WorkflowStatus,
)
from libraries.utils import make_canonical_id, make_prefixed_id
from services.backtest_reconciliation.loaders import (
    latest_portfolio_proposal_review_decision_time,
    load_backtest_runs,
    load_cost_models,
    load_execution_timing_rules,
    load_fill_assumptions,
    load_paper_trades,
    load_portfolio_proposals,
    load_realism_warnings,
    load_signals,
    proposal_company_id,
)
from services.backtest_reconciliation.rules import (
    build_approval_delay_warning,
    build_backtest_cost_model,
    build_backtest_execution_timing_rule,
    build_backtest_fill_assumption,
    build_backtest_realism_warnings,
    build_paper_cost_model,
    build_paper_execution_timing_rule,
    build_paper_fill_assumption,
    build_paper_realism_warnings,
    build_reconciliation_summary,
    build_strategy_to_paper_mapping,
    detect_assumption_mismatches,
    detect_availability_mismatches,
    highest_severity,
)
from services.backtest_reconciliation.storage import LocalBacktestReconciliationArtifactStore
from services.experiment_registry import (
    AppendExperimentContextRequest,
    ExperimentRegistryService,
)
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)


class RealismArtifactBundle(StrictModel):
    """Shared bundle returned when one workflow emits realism artifacts."""

    execution_timing_rule: ExecutionTimingRule = Field(
        description="Execution timing rule recorded for the workflow scope."
    )
    fill_assumption: FillAssumption = Field(
        description="Fill assumption recorded for the workflow scope."
    )
    cost_model: CostModel = Field(description="Cost model recorded for the workflow scope.")
    realism_warnings: list[RealismWarning] = Field(
        default_factory=list,
        description="Realism warnings recorded for the workflow scope.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Storage locations written while persisting the realism artifacts.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes attached to the realism bundle.",
    )


class RunBacktestPaperReconciliationRequest(StrictModel):
    """Request to compare one backtest context to one proposal and optional paper trades."""

    backtesting_root: Path = Field(description="Root path containing persisted backtesting artifacts.")
    portfolio_root: Path = Field(description="Root path containing persisted portfolio artifacts.")
    review_root: Path | None = Field(
        default=None,
        description="Optional review root used to resolve proposal approval timing.",
    )
    experiments_root: Path | None = Field(
        default=None,
        description="Optional experiment root used to append reconciliation context.",
    )
    monitoring_root: Path | None = Field(
        default=None,
        description="Optional monitoring root used for run summaries.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional reconciliation output root.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when roots contain multiple companies or proposals.",
    )
    backtest_run_id: str | None = Field(
        default=None,
        description="Explicit backtest run identifier to reconcile.",
    )
    portfolio_proposal_id: str | None = Field(
        default=None,
        description="Explicit portfolio proposal identifier to reconcile.",
    )
    paper_trade_ids: list[str] = Field(
        default_factory=list,
        description="Optional paper-trade identifiers to restrict the compared paper side.",
    )
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional creation-time cutoff applied while loading candidate artifacts.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunBacktestPaperReconciliationResponse(StrictModel):
    """Structured response returned after comparing backtest and paper paths."""

    backtest_execution_timing_rule: ExecutionTimingRule | None = Field(
        default=None,
        description="Backtest-side timing rule used by the comparison when available.",
    )
    paper_execution_timing_rule: ExecutionTimingRule = Field(
        description="Paper-side timing rule used by the comparison."
    )
    backtest_fill_assumption: FillAssumption | None = Field(
        default=None,
        description="Backtest-side fill assumption used by the comparison when available.",
    )
    paper_fill_assumption: FillAssumption = Field(
        description="Paper-side fill assumption used by the comparison."
    )
    backtest_cost_model: CostModel | None = Field(
        default=None,
        description="Backtest-side cost model used by the comparison when available.",
    )
    paper_cost_model: CostModel = Field(description="Paper-side cost model used by the comparison.")
    strategy_to_paper_mapping: StrategyToPaperMapping = Field(
        description="Persisted mapping linking the compared workflows."
    )
    reconciliation_report: ReconciliationReport = Field(
        description="Parent reconciliation report for the comparison."
    )
    assumption_mismatches: list[AssumptionMismatch] = Field(
        default_factory=list,
        description="Structured assumption mismatches recorded for the comparison.",
    )
    availability_mismatches: list[AvailabilityMismatch] = Field(
        default_factory=list,
        description="Structured availability mismatches recorded for the comparison.",
    )
    realism_warnings: list[RealismWarning] = Field(
        default_factory=list,
        description="Combined realism warnings recorded for the compared workflows.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Storage locations written while persisting the reconciliation result.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes attached to the comparison.",
    )


class BacktestReconciliationService(BaseService):
    """Persist realism assumptions and reconcile backtest and paper workflow semantics."""

    capability_name = "backtest_reconciliation"
    capability_description = (
        "Records execution realism assumptions and compares backtest timing and paper workflow semantics."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["BacktestRun", "PortfolioProposal", "PaperTrade"],
            produces=[
                "ExecutionTimingRule",
                "FillAssumption",
                "CostModel",
                "StrategyToPaperMapping",
                "ReconciliationReport",
            ],
            api_routes=[],
        )

    def build_backtest_realism_context(
        self,
        *,
        backtest_run_id: str,
        company_id: str,
        execution_assumption: ExecutionAssumption,
        source_reference_ids: list[str],
        output_root: Path | None = None,
        workflow_run_id: str | None = None,
    ) -> RealismArtifactBundle:
        """Persist one explicit backtest-side realism bundle."""

        resolved_run_id = workflow_run_id or backtest_run_id
        reconciliation_root = output_root or resolve_artifact_workspace().reconciliation_root
        store = LocalBacktestReconciliationArtifactStore(root=reconciliation_root, clock=self.clock)
        timing_rule = build_backtest_execution_timing_rule(
            company_id=company_id,
            backtest_run_id=backtest_run_id,
            execution_assumption=execution_assumption,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
            source_reference_ids=source_reference_ids,
        )
        fill_assumption = build_backtest_fill_assumption(
            company_id=company_id,
            backtest_run_id=backtest_run_id,
            execution_assumption=execution_assumption,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
            source_reference_ids=source_reference_ids,
        )
        cost_model = build_backtest_cost_model(
            company_id=company_id,
            backtest_run_id=backtest_run_id,
            execution_assumption=execution_assumption,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
            source_reference_ids=source_reference_ids,
        )
        warnings = build_backtest_realism_warnings(
            backtest_run_id=backtest_run_id,
            company_id=company_id,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
            source_reference_ids=source_reference_ids,
        )
        storage_locations = [
            store.persist_model(
                artifact_id=timing_rule.execution_timing_rule_id,
                category="execution_timing_rules",
                model=timing_rule,
                source_reference_ids=timing_rule.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=fill_assumption.fill_assumption_id,
                category="fill_assumptions",
                model=fill_assumption,
                source_reference_ids=fill_assumption.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=cost_model.cost_model_id,
                category="cost_models",
                model=cost_model,
                source_reference_ids=cost_model.provenance.source_reference_ids,
            ),
        ]
        for warning in warnings:
            storage_locations.append(
                store.persist_model(
                    artifact_id=warning.realism_warning_id,
                    category="realism_warnings",
                    model=warning,
                    source_reference_ids=warning.provenance.source_reference_ids,
                )
            )
        return RealismArtifactBundle(
            execution_timing_rule=timing_rule,
            fill_assumption=fill_assumption,
            cost_model=cost_model,
            realism_warnings=warnings,
            storage_locations=storage_locations,
            notes=[
                f"backtest_execution_timing_rule_id={timing_rule.execution_timing_rule_id}",
                f"backtest_fill_assumption_id={fill_assumption.fill_assumption_id}",
                f"backtest_cost_model_id={cost_model.cost_model_id}",
            ],
        )

    def build_paper_realism_context(
        self,
        *,
        portfolio_proposal: PortfolioProposal,
        proposed_trades: list[PaperTrade],
        trade_batch_id: str,
        output_root: Path | None = None,
        workflow_run_id: str | None = None,
    ) -> RealismArtifactBundle:
        """Persist one explicit paper-side realism bundle."""

        resolved_run_id = workflow_run_id or trade_batch_id
        reconciliation_root = output_root or resolve_artifact_workspace().reconciliation_root
        store = LocalBacktestReconciliationArtifactStore(root=reconciliation_root, clock=self.clock)
        timing_rule = build_paper_execution_timing_rule(
            portfolio_proposal=portfolio_proposal,
            trade_batch_id=trade_batch_id,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
        )
        fill_assumption = build_paper_fill_assumption(
            portfolio_proposal=portfolio_proposal,
            proposed_trades=proposed_trades,
            trade_batch_id=trade_batch_id,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
        )
        cost_model = build_paper_cost_model(
            portfolio_proposal=portfolio_proposal,
            proposed_trades=proposed_trades,
            trade_batch_id=trade_batch_id,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
        )
        warnings = build_paper_realism_warnings(
            portfolio_proposal=portfolio_proposal,
            proposed_trades=proposed_trades,
            clock=self.clock,
            workflow_run_id=resolved_run_id,
        )
        storage_locations = [
            store.persist_model(
                artifact_id=timing_rule.execution_timing_rule_id,
                category="execution_timing_rules",
                model=timing_rule,
                source_reference_ids=timing_rule.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=fill_assumption.fill_assumption_id,
                category="fill_assumptions",
                model=fill_assumption,
                source_reference_ids=fill_assumption.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=cost_model.cost_model_id,
                category="cost_models",
                model=cost_model,
                source_reference_ids=cost_model.provenance.source_reference_ids,
            ),
        ]
        for warning in warnings:
            storage_locations.append(
                store.persist_model(
                    artifact_id=warning.realism_warning_id,
                    category="realism_warnings",
                    model=warning,
                    source_reference_ids=warning.provenance.source_reference_ids,
                )
            )
        return RealismArtifactBundle(
            execution_timing_rule=timing_rule,
            fill_assumption=fill_assumption,
            cost_model=cost_model,
            realism_warnings=warnings,
            storage_locations=storage_locations,
            notes=[
                f"paper_execution_timing_rule_id={timing_rule.execution_timing_rule_id}",
                f"paper_fill_assumption_id={fill_assumption.fill_assumption_id}",
                f"paper_cost_model_id={cost_model.cost_model_id}",
            ],
        )

    def run_backtest_paper_reconciliation(
        self,
        request: RunBacktestPaperReconciliationRequest,
    ) -> RunBacktestPaperReconciliationResponse:
        """Compare one backtest context to one proposal and optional paper trades."""

        workspace = self._resolve_workspace(request=request)
        reconciliation_root = request.output_root or workspace.reconciliation_root
        monitoring_root = request.monitoring_root or workspace.monitoring_root
        experiments_root = request.experiments_root or workspace.experiments_root
        review_root = request.review_root or workspace.review_root
        workflow_run_id = make_prefixed_id("reconcile")
        monitoring_service = MonitoringService(clock=self.clock)
        started_at = self.clock.now()
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="backtest_paper_reconciliation",
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message="Backtest-to-paper reconciliation started.",
                related_artifact_ids=[],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        try:
            response = self._run_backtest_paper_reconciliation_impl(
                request=request,
                workspace=workspace,
                review_root=review_root,
                reconciliation_root=reconciliation_root,
                experiments_root=experiments_root,
                workflow_run_id=workflow_run_id,
            )
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="backtest_paper_reconciliation",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=f"Backtest-to-paper reconciliation failed: {exc}",
                    related_artifact_ids=[],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="backtest_paper_reconciliation",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=[],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=["Reconciliation failed before a report could be persisted."],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise

        completed_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="backtest_paper_reconciliation",
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_COMPLETED,
                status=WorkflowStatus.SUCCEEDED,
                message="Backtest-to-paper reconciliation completed.",
                related_artifact_ids=[
                    response.strategy_to_paper_mapping.strategy_to_paper_mapping_id,
                    response.reconciliation_report.reconciliation_report_id,
                ],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        pipeline_event_ids = [
            start_event.pipeline_event.pipeline_event_id,
            completed_event.pipeline_event.pipeline_event_id,
        ]
        summary_status = WorkflowStatus.SUCCEEDED
        attention_reasons: list[str] = []
        combined_mismatches: list[AssumptionMismatch | AvailabilityMismatch] = [
            *response.assumption_mismatches,
            *response.availability_mismatches,
        ]
        if any(
            mismatch.severity in {Severity.HIGH, Severity.CRITICAL}
            for mismatch in combined_mismatches
        ):
            attention_reasons.append("reconciliation_high_severity_mismatch")
        if attention_reasons:
            attention_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="backtest_paper_reconciliation",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.ATTENTION_REQUIRED,
                    status=WorkflowStatus.ATTENTION_REQUIRED,
                    message=response.reconciliation_report.summary,
                    related_artifact_ids=[
                        response.strategy_to_paper_mapping.strategy_to_paper_mapping_id,
                        response.reconciliation_report.reconciliation_report_id,
                    ],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            pipeline_event_ids.append(attention_event.pipeline_event.pipeline_event_id)
            summary_status = WorkflowStatus.ATTENTION_REQUIRED
        monitoring_service.record_run_summary(
            RecordRunSummaryRequest(
                workflow_name="backtest_paper_reconciliation",
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                requested_by=request.requested_by,
                status=summary_status,
                started_at=started_at,
                completed_at=self.clock.now(),
                storage_locations=response.storage_locations,
                produced_artifact_ids=[
                    response.strategy_to_paper_mapping.strategy_to_paper_mapping_id,
                    response.reconciliation_report.reconciliation_report_id,
                    *[mismatch.assumption_mismatch_id for mismatch in response.assumption_mismatches],
                    *[
                        mismatch.availability_mismatch_id
                        for mismatch in response.availability_mismatches
                    ],
                    *[warning.realism_warning_id for warning in response.realism_warnings],
                ],
                pipeline_event_ids=pipeline_event_ids,
                attention_reasons=attention_reasons,
                notes=response.notes,
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        return response

    def _run_backtest_paper_reconciliation_impl(
        self,
        *,
        request: RunBacktestPaperReconciliationRequest,
        workspace: ArtifactWorkspace,
        review_root: Path,
        reconciliation_root: Path,
        experiments_root: Path,
        workflow_run_id: str,
    ) -> RunBacktestPaperReconciliationResponse:
        store = LocalBacktestReconciliationArtifactStore(root=reconciliation_root, clock=self.clock)
        signals = {signal.signal_id: signal for signal in self._load_signals(workspace=workspace)}
        proposal = self._resolve_portfolio_proposal(request=request)
        company_id = request.company_id or proposal_company_id(proposal)
        if company_id is None:
            raise ValueError(
                "Backtest reconciliation requires an explicit company_id when proposal company scope cannot be derived."
            )
        backtest_run = self._resolve_backtest_run(request=request, company_id=company_id)
        paper_trades = self._resolve_paper_trades(request=request, proposal=proposal)
        proposal_review_decided_at = self._proposal_review_decided_at(
            review_root=review_root,
            portfolio_root=request.portfolio_root,
            proposal_id=proposal.portfolio_proposal_id,
        )

        backtest_timing_rule = self._load_execution_timing_rule(
            reconciliation_root=reconciliation_root,
            rule_id=backtest_run.execution_timing_rule_id,
            workflow_scope="backtest",
            portfolio_proposal_id=proposal.portfolio_proposal_id,
        )
        paper_timing_rule = self._load_execution_timing_rule(
            reconciliation_root=reconciliation_root,
            rule_id=next(
                (
                    trade.execution_timing_rule_id
                    for trade in paper_trades
                    if trade.execution_timing_rule_id is not None
                ),
                None,
            ),
            workflow_scope="paper",
            portfolio_proposal_id=proposal.portfolio_proposal_id,
        )
        if paper_timing_rule is None:
            raise ValueError(
                "No paper-side execution timing rule was found for the selected portfolio proposal."
            )
        backtest_fill_assumption = self._load_fill_assumption(
            reconciliation_root=reconciliation_root,
            assumption_id=backtest_run.fill_assumption_id,
            workflow_scope="backtest",
            portfolio_proposal_id=proposal.portfolio_proposal_id,
        )
        paper_fill_assumption = self._load_fill_assumption(
            reconciliation_root=reconciliation_root,
            assumption_id=next(
                (trade.fill_assumption_id for trade in paper_trades if trade.fill_assumption_id is not None),
                None,
            ),
            workflow_scope="paper",
            portfolio_proposal_id=proposal.portfolio_proposal_id,
        )
        if paper_fill_assumption is None:
            raise ValueError(
                "No paper-side fill assumption was found for the selected portfolio proposal."
            )
        backtest_cost_model = self._load_cost_model(
            reconciliation_root=reconciliation_root,
            cost_model_id=backtest_run.cost_model_id,
            workflow_scope="backtest",
            portfolio_proposal_id=proposal.portfolio_proposal_id,
        )
        paper_cost_model = self._load_cost_model(
            reconciliation_root=reconciliation_root,
            cost_model_id=next(
                (trade.cost_model_id for trade in paper_trades if trade.cost_model_id is not None),
                None,
            ),
            workflow_scope="paper",
            portfolio_proposal_id=proposal.portfolio_proposal_id,
        )
        if paper_cost_model is None:
            raise ValueError(
                "No paper-side cost model was found for the selected portfolio proposal."
            )

        signal_ids = list(dict.fromkeys(idea.signal_id for idea in proposal.position_ideas))
        source_reference_ids = sorted(
            {
                *proposal.provenance.source_reference_ids,
                *backtest_run.provenance.source_reference_ids,
                *(
                    source_reference_id
                    for trade in paper_trades
                    for source_reference_id in trade.provenance.source_reference_ids
                ),
            }
        )
        mapping = build_strategy_to_paper_mapping(
            company_id=company_id,
            backtest_run_id=backtest_run.backtest_run_id,
            portfolio_proposal=proposal,
            paper_trades=paper_trades,
            signal_ids=signal_ids,
            matched_signal_family=backtest_run.signal_family,
            matched_ablation_view=backtest_run.ablation_view.value,
            backtest_execution_timing_rule=backtest_timing_rule,
            paper_execution_timing_rule=paper_timing_rule,
            backtest_fill_assumption=backtest_fill_assumption,
            paper_fill_assumption=paper_fill_assumption,
            backtest_cost_model=backtest_cost_model,
            paper_cost_model=paper_cost_model,
            notes=[
                f"portfolio_proposal_id={proposal.portfolio_proposal_id}",
                f"backtest_run_id={backtest_run.backtest_run_id}",
                (
                    f"proposal_review_decided_at={proposal_review_decided_at.isoformat()}"
                    if proposal_review_decided_at is not None
                    else "proposal_review_decided_at=none"
                ),
            ],
            clock=self.clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        )
        assumption_mismatches = detect_assumption_mismatches(
            company_id=company_id,
            mapping=mapping,
            backtest_execution_timing_rule=backtest_timing_rule,
            paper_execution_timing_rule=paper_timing_rule,
            backtest_fill_assumption=backtest_fill_assumption,
            paper_fill_assumption=paper_fill_assumption,
            backtest_cost_model=backtest_cost_model,
            paper_cost_model=paper_cost_model,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        )
        availability_mismatches = detect_availability_mismatches(
            company_id=company_id,
            mapping=mapping,
            portfolio_proposal=proposal,
            paper_trades=paper_trades,
            signals_by_id=signals,
            backtest_run_decision_cutoff_time=backtest_run.decision_cutoff_time,
            proposal_review_decided_at=proposal_review_decided_at,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        )
        workflow_warnings = [
            warning
            for warning in load_realism_warnings(reconciliation_root)
            if (
                proposal.portfolio_proposal_id in warning.related_artifact_ids
                or backtest_run.backtest_run_id in warning.related_artifact_ids
            )
        ]
        if proposal_review_decided_at is None or proposal_review_decided_at > proposal.as_of_time:
            workflow_warnings.append(
                build_approval_delay_warning(
                    portfolio_proposal=proposal,
                    backtest_run_id=backtest_run.backtest_run_id,
                    paper_trades=paper_trades,
                    clock=self.clock,
                    workflow_run_id=workflow_run_id,
                )
            )

        all_warnings = list(
            {warning.realism_warning_id: warning for warning in workflow_warnings}.values()
        )
        report_mismatches: list[AssumptionMismatch | AvailabilityMismatch] = [
            *assumption_mismatches,
            *availability_mismatches,
        ]
        summary = build_reconciliation_summary(
            mismatches=report_mismatches,
            warnings=all_warnings,
        )
        report = ReconciliationReport(
            reconciliation_report_id=make_canonical_id(
                "rreport",
                company_id,
                mapping.strategy_to_paper_mapping_id,
            ),
            company_id=company_id,
            strategy_to_paper_mapping_id=mapping.strategy_to_paper_mapping_id,
            assumption_mismatch_ids=[
                mismatch.assumption_mismatch_id for mismatch in assumption_mismatches
            ],
            availability_mismatch_ids=[
                mismatch.availability_mismatch_id for mismatch in availability_mismatches
            ],
            realism_warning_ids=[warning.realism_warning_id for warning in all_warnings],
            highest_severity=highest_severity(
                mismatches=report_mismatches,
                warnings=all_warnings,
            ),
            internally_consistent=not any(mismatch.blocking for mismatch in report_mismatches),
            review_required=bool(assumption_mismatches or availability_mismatches or all_warnings),
            summary=summary,
            provenance=mapping.provenance.model_copy(
                update={
                    "transformation_name": "day24_backtest_paper_reconciliation_report",
                    "upstream_artifact_ids": [
                        mapping.strategy_to_paper_mapping_id,
                        proposal.portfolio_proposal_id,
                        backtest_run.backtest_run_id,
                    ],
                    "notes": [summary],
                }
            ),
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        storage_locations = [
            store.persist_model(
                artifact_id=mapping.strategy_to_paper_mapping_id,
                category="strategy_to_paper_mappings",
                model=mapping,
                source_reference_ids=mapping.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=report.reconciliation_report_id,
                category="reconciliation_reports",
                model=report,
                source_reference_ids=report.provenance.source_reference_ids,
            ),
        ]
        for mismatch in assumption_mismatches:
            storage_locations.append(
                store.persist_model(
                    artifact_id=mismatch.assumption_mismatch_id,
                    category="assumption_mismatches",
                    model=mismatch,
                    source_reference_ids=mismatch.provenance.source_reference_ids,
                )
            )
        for availability_mismatch in availability_mismatches:
            storage_locations.append(
                store.persist_model(
                    artifact_id=availability_mismatch.availability_mismatch_id,
                    category="availability_mismatches",
                    model=availability_mismatch,
                    source_reference_ids=availability_mismatch.provenance.source_reference_ids,
                )
            )
        existing_warning_ids = {warning.realism_warning_id for warning in load_realism_warnings(reconciliation_root)}
        for warning in all_warnings:
            if warning.realism_warning_id in existing_warning_ids:
                continue
            storage_locations.append(
                store.persist_model(
                    artifact_id=warning.realism_warning_id,
                    category="realism_warnings",
                    model=warning,
                    source_reference_ids=warning.provenance.source_reference_ids,
                )
            )

        if backtest_run.experiment_id is not None:
            experiment_artifacts = self._build_experiment_context_artifacts(
                backtest_run=backtest_run,
                report=report,
                mapping=mapping,
                backtest_execution_timing_rule=backtest_timing_rule,
                paper_execution_timing_rule=paper_timing_rule,
                backtest_fill_assumption=backtest_fill_assumption,
                paper_fill_assumption=paper_fill_assumption,
                backtest_cost_model=backtest_cost_model,
                paper_cost_model=paper_cost_model,
                assumption_mismatches=assumption_mismatches,
                availability_mismatches=availability_mismatches,
                realism_warnings=all_warnings,
                reconciliation_root=reconciliation_root,
                workflow_run_id=workflow_run_id,
            )
            append_response = ExperimentRegistryService(clock=self.clock).append_experiment_context(
                AppendExperimentContextRequest(
                    experiment_id=backtest_run.experiment_id,
                    experiment_artifacts=experiment_artifacts,
                    notes=[
                        f"reconciliation_report_id={report.reconciliation_report_id}",
                        f"strategy_to_paper_mapping_id={mapping.strategy_to_paper_mapping_id}",
                    ],
                ),
                output_root=experiments_root,
            )
            storage_locations.extend(append_response.storage_locations)

        notes = [
            f"requested_by={request.requested_by}",
            f"reconciliation_report_id={report.reconciliation_report_id}",
            f"strategy_to_paper_mapping_id={mapping.strategy_to_paper_mapping_id}",
            f"assumption_mismatch_count={len(assumption_mismatches)}",
            f"availability_mismatch_count={len(availability_mismatches)}",
            f"realism_warning_count={len(all_warnings)}",
        ]
        return RunBacktestPaperReconciliationResponse(
            backtest_execution_timing_rule=backtest_timing_rule,
            paper_execution_timing_rule=paper_timing_rule,
            backtest_fill_assumption=backtest_fill_assumption,
            paper_fill_assumption=paper_fill_assumption,
            backtest_cost_model=backtest_cost_model,
            paper_cost_model=paper_cost_model,
            strategy_to_paper_mapping=mapping,
            reconciliation_report=report,
            assumption_mismatches=assumption_mismatches,
            availability_mismatches=availability_mismatches,
            realism_warnings=all_warnings,
            storage_locations=storage_locations,
            notes=notes,
        )

    def _resolve_workspace(
        self,
        *,
        request: RunBacktestPaperReconciliationRequest,
    ) -> ArtifactWorkspace:
        anchors = [
            root
            for root in (
                request.output_root,
                request.backtesting_root,
                request.portfolio_root,
                request.review_root,
                request.experiments_root,
                request.monitoring_root,
            )
            if root is not None
        ]
        if not anchors:
            return resolve_artifact_workspace()
        workspace_parents = {anchor.resolve().parent for anchor in anchors}
        if len(workspace_parents) != 1:
            raise ValueError(
                "Backtest reconciliation roots must belong to the same artifact workspace when mixed explicit roots are supplied."
            )
        return resolve_artifact_workspace_from_stage_root(anchors[0])

    def _resolve_portfolio_proposal(
        self,
        *,
        request: RunBacktestPaperReconciliationRequest,
    ) -> PortfolioProposal:
        proposals = load_portfolio_proposals(
            portfolio_root=request.portfolio_root,
            company_id=request.company_id,
            as_of_time=request.as_of_time,
        )
        if request.portfolio_proposal_id is not None:
            for proposal in proposals:
                if proposal.portfolio_proposal_id == request.portfolio_proposal_id:
                    return proposal
            raise ValueError(
                f"Portfolio proposal `{request.portfolio_proposal_id}` was not found under the portfolio root."
            )
        if len(proposals) != 1:
            raise ValueError(
                "Backtest reconciliation requires an explicit portfolio_proposal_id when the portfolio root contains zero or multiple plausible proposals."
            )
        return proposals[0]

    def _resolve_backtest_run(
        self,
        *,
        request: RunBacktestPaperReconciliationRequest,
        company_id: str,
    ) -> BacktestRun:
        runs = load_backtest_runs(
            backtesting_root=request.backtesting_root,
            company_id=company_id,
            as_of_time=request.as_of_time,
        )
        if request.backtest_run_id is not None:
            for run in runs:
                if run.backtest_run_id == request.backtest_run_id:
                    return run
            raise ValueError(
                f"Backtest run `{request.backtest_run_id}` was not found under the backtesting root."
            )
        if len(runs) != 1:
            raise ValueError(
                "Backtest reconciliation requires an explicit backtest_run_id when the backtesting root contains zero or multiple plausible runs."
            )
        return runs[0]

    def _resolve_paper_trades(
        self,
        *,
        request: RunBacktestPaperReconciliationRequest,
        proposal: PortfolioProposal,
    ) -> list[PaperTrade]:
        trades = load_paper_trades(
            portfolio_root=request.portfolio_root,
            proposal_id=proposal.portfolio_proposal_id,
            as_of_time=request.as_of_time,
        )
        if not request.paper_trade_ids:
            return trades
        trade_ids = set(request.paper_trade_ids)
        matched = [trade for trade in trades if trade.paper_trade_id in trade_ids]
        if len(matched) != len(trade_ids):
            missing = sorted(trade_ids - {trade.paper_trade_id for trade in matched})
            raise ValueError(
                "Some requested paper_trade_ids were not found for the selected proposal: "
                + ", ".join(missing)
            )
        return matched

    def _load_execution_timing_rule(
        self,
        *,
        reconciliation_root: Path,
        rule_id: str | None,
        workflow_scope: str,
        portfolio_proposal_id: str,
    ) -> ExecutionTimingRule | None:
        rules = load_execution_timing_rules(reconciliation_root)
        if rule_id is not None:
            for rule in rules:
                if rule.execution_timing_rule_id == rule_id:
                    return rule
        scope_value = workflow_scope if workflow_scope != "paper" else "paper_trading"
        candidates = [
            rule
            for rule in rules
            if (
                rule.workflow_scope.value == scope_value
                and portfolio_proposal_id in rule.provenance.upstream_artifact_ids
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate.created_at)

    def _load_fill_assumption(
        self,
        *,
        reconciliation_root: Path,
        assumption_id: str | None,
        workflow_scope: str,
        portfolio_proposal_id: str,
    ) -> FillAssumption | None:
        assumptions = load_fill_assumptions(reconciliation_root)
        if assumption_id is not None:
            for assumption in assumptions:
                if assumption.fill_assumption_id == assumption_id:
                    return assumption
        scope_value = workflow_scope if workflow_scope != "paper" else "paper_trading"
        candidates = [
            assumption
            for assumption in assumptions
            if (
                assumption.workflow_scope.value == scope_value
                and portfolio_proposal_id in assumption.provenance.upstream_artifact_ids
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate.created_at)

    def _load_cost_model(
        self,
        *,
        reconciliation_root: Path,
        cost_model_id: str | None,
        workflow_scope: str,
        portfolio_proposal_id: str,
    ) -> CostModel | None:
        cost_models = load_cost_models(reconciliation_root)
        if cost_model_id is not None:
            for cost_model in cost_models:
                if cost_model.cost_model_id == cost_model_id:
                    return cost_model
        scope_value = workflow_scope if workflow_scope != "paper" else "paper_trading"
        candidates = [
            cost_model
            for cost_model in cost_models
            if (
                cost_model.workflow_scope.value == scope_value
                and portfolio_proposal_id in cost_model.provenance.upstream_artifact_ids
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate.created_at)

    def _load_signals(self, *, workspace: ArtifactWorkspace) -> list[Signal]:
        return load_signals(workspace.signal_root)

    def _proposal_review_decided_at(
        self,
        *,
        review_root: Path,
        portfolio_root: Path,
        proposal_id: str,
    ) -> datetime | None:
        return latest_portfolio_proposal_review_decision_time(
            review_root=review_root,
            portfolio_root=portfolio_root,
            proposal_id=proposal_id,
        )

    def _build_experiment_context_artifacts(
        self,
        *,
        backtest_run: BacktestRun,
        report: ReconciliationReport,
        mapping: StrategyToPaperMapping,
        backtest_execution_timing_rule: ExecutionTimingRule | None,
        paper_execution_timing_rule: ExecutionTimingRule,
        backtest_fill_assumption: FillAssumption | None,
        paper_fill_assumption: FillAssumption,
        backtest_cost_model: CostModel | None,
        paper_cost_model: CostModel,
        assumption_mismatches: list[AssumptionMismatch],
        availability_mismatches: list[AvailabilityMismatch],
        realism_warnings: list[RealismWarning],
        reconciliation_root: Path,
        workflow_run_id: str,
    ) -> list[ExperimentArtifact]:
        artifacts: list[tuple[str, str, ExperimentArtifactRole]] = [
            (report.reconciliation_report_id, "ReconciliationReport", ExperimentArtifactRole.SUMMARY),
            (
                mapping.strategy_to_paper_mapping_id,
                "StrategyToPaperMapping",
                ExperimentArtifactRole.DIAGNOSTIC,
            ),
            (
                paper_execution_timing_rule.execution_timing_rule_id,
                "ExecutionTimingRule",
                ExperimentArtifactRole.DIAGNOSTIC,
            ),
            (
                paper_fill_assumption.fill_assumption_id,
                "FillAssumption",
                ExperimentArtifactRole.DIAGNOSTIC,
            ),
            (paper_cost_model.cost_model_id, "CostModel", ExperimentArtifactRole.DIAGNOSTIC),
            *[
                (mismatch.assumption_mismatch_id, "AssumptionMismatch", ExperimentArtifactRole.DIAGNOSTIC)
                for mismatch in assumption_mismatches
            ],
            *[
                (mismatch.availability_mismatch_id, "AvailabilityMismatch", ExperimentArtifactRole.DIAGNOSTIC)
                for mismatch in availability_mismatches
            ],
            *[
                (warning.realism_warning_id, "RealismWarning", ExperimentArtifactRole.DIAGNOSTIC)
                for warning in realism_warnings
            ],
        ]
        if backtest_execution_timing_rule is not None:
            artifacts.append(
                (
                    backtest_execution_timing_rule.execution_timing_rule_id,
                    "ExecutionTimingRule",
                    ExperimentArtifactRole.DIAGNOSTIC,
                )
            )
        if backtest_fill_assumption is not None:
            artifacts.append(
                (
                    backtest_fill_assumption.fill_assumption_id,
                    "FillAssumption",
                    ExperimentArtifactRole.DIAGNOSTIC,
                )
            )
        if backtest_cost_model is not None:
            artifacts.append(
                (
                    backtest_cost_model.cost_model_id,
                    "CostModel",
                    ExperimentArtifactRole.DIAGNOSTIC,
                )
            )
        now = self.clock.now()
        return [
            ExperimentArtifact(
                experiment_artifact_id=make_canonical_id(
                    "eart",
                    backtest_run.experiment_id or backtest_run.backtest_run_id,
                    artifact_type,
                    artifact_id,
                ),
                experiment_id=backtest_run.experiment_id or "missing_experiment",
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                artifact_role=artifact_role,
                artifact_storage_location_id=None,
                uri=(reconciliation_root / self._category_for_artifact_type(artifact_type) / f"{artifact_id}.json").resolve().as_uri(),
                produced_at=now,
                provenance=report.provenance.model_copy(
                    update={
                        "transformation_name": "day24_experiment_artifact_from_reconciliation",
                        "upstream_artifact_ids": [report.reconciliation_report_id, artifact_id],
                        "workflow_run_id": workflow_run_id,
                    }
                ),
                created_at=now,
                updated_at=now,
            )
            for artifact_id, artifact_type, artifact_role in artifacts
        ]

    def _category_for_artifact_type(self, artifact_type: str) -> str:
        return {
            "ReconciliationReport": "reconciliation_reports",
            "StrategyToPaperMapping": "strategy_to_paper_mappings",
            "ExecutionTimingRule": "execution_timing_rules",
            "FillAssumption": "fill_assumptions",
            "CostModel": "cost_models",
            "AssumptionMismatch": "assumption_mismatches",
            "AvailabilityMismatch": "availability_mismatches",
            "RealismWarning": "realism_warnings",
        }[artifact_type]
