from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from libraries.core import load_local_models, resolve_artifact_workspace
from libraries.schemas import (
    AblationView,
    ArtifactStorageLocation,
    DailyPaperSummary,
    DailySystemReport,
    DataRefreshMode,
    ManualInterventionRequirement,
    PortfolioProposalStatus,
    ProposalScorecard,
    QualityDecision,
    RefusalReason,
    ReviewFollowup,
    ReviewFollowupStatus,
    RiskSummary,
    WorkflowStatus,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import (
    FeatureSignalPipelineResponse,
    run_feature_signal_pipeline,
)
from services.daily_orchestration.definitions import DEFAULT_FIXTURES_ROOT
from services.ingestion import FixtureIngestionResponse
from services.monitoring import (
    ListRecentRunSummariesRequest,
    ListRecentRunSummariesResponse,
    MonitoringService,
    RunHealthChecksRequest,
    RunHealthChecksResponse,
)
from services.operator_review import (
    OperatorReviewService,
    SyncReviewQueueRequest,
    SyncReviewQueueResponse,
)
from services.paper_execution import (
    PaperExecutionService,
    PaperTradeProposalRequest,
    PaperTradeProposalResponse,
)
from services.parsing import ExtractDocumentEvidenceResponse
from services.portfolio import (
    PortfolioConstructionService,
    RunPortfolioWorkflowRequest,
    RunPortfolioWorkflowResponse,
)
from services.portfolio.storage import LocalPortfolioArtifactStore
from services.reporting import (
    GenerateDailySystemReportRequest,
    GenerateProposalScorecardRequest,
    GenerateReviewQueueSummaryRequest,
    GenerateRiskSummaryRequest,
    ReportingService,
)
from services.reporting.loaders import load_reporting_workspace
from services.research_orchestrator import RunResearchWorkflowResponse


@dataclass
class WorkflowRoots:
    """Resolved artifact roots used by the daily workflow."""

    artifact_root: Path
    ingestion_root: Path
    parsing_root: Path
    research_root: Path
    signal_root: Path
    signal_arbitration_root: Path
    portfolio_root: Path
    portfolio_analysis_root: Path
    review_root: Path
    audit_root: Path
    monitoring_root: Path
    data_quality_root: Path
    orchestration_root: Path
    backtesting_root: Path
    reporting_root: Path


@dataclass
class DailyWorkflowContext:
    """Execution context shared by all step executors."""

    artifact_root: Path
    fixtures_root: Path | None
    data_refresh_mode: DataRefreshMode
    company_id: str | None
    as_of_time: datetime | None
    generate_memo_skeleton: bool
    include_retrieval_context: bool
    ablation_view: AblationView
    assumed_reference_prices: dict[str, float]
    requested_by: str
    roots: WorkflowRoots
    clock: Clock


@dataclass
class DailyWorkflowOutputs:
    """Typed child workflow outputs accumulated during orchestration."""

    fixture_refresh_and_normalization: list[FixtureIngestionResponse] = field(default_factory=list)
    evidence_extraction: list[ExtractDocumentEvidenceResponse] = field(default_factory=list)
    research_workflow: RunResearchWorkflowResponse | None = None
    feature_signal_pipeline: FeatureSignalPipelineResponse | None = None
    portfolio_workflow: RunPortfolioWorkflowResponse | None = None
    risk_summary: RiskSummary | None = None
    proposal_scorecard: ProposalScorecard | None = None
    review_queue_sync: SyncReviewQueueResponse | None = None
    paper_trade_candidate_generation: PaperTradeProposalResponse | None = None
    operations_health_checks: RunHealthChecksResponse | None = None
    recent_run_summaries: ListRecentRunSummariesResponse | None = None
    daily_system_report: DailySystemReport | None = None


@dataclass
class DailyWorkflowState:
    """Mutable state threaded through the orchestration steps."""

    context: DailyWorkflowContext
    outputs: DailyWorkflowOutputs = field(default_factory=DailyWorkflowOutputs)
    resolved_company_id: str | None = None


@dataclass
class StepExecutionOutcome:
    """Internal execution result for one orchestration step."""

    status: WorkflowStatus
    notes: list[str] = field(default_factory=list)
    child_workflow_ids: list[str] = field(default_factory=list)
    child_run_summary_ids: list[str] = field(default_factory=list)
    produced_artifact_ids: list[str] = field(default_factory=list)
    manual_intervention_requirement: ManualInterventionRequirement | None = None
    stop_workflow: bool = False


def execute_fixture_refresh_and_normalization(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Refresh fixture-backed ingestion state or reuse an existing ingestion slice."""

    context = state.context
    if context.data_refresh_mode is DataRefreshMode.REUSE_EXISTING_INGESTION:
        return StepExecutionOutcome(
            status=WorkflowStatus.SUCCEEDED,
            notes=[
                "Reused existing ingestion artifacts; fixture refresh was skipped.",
                f"ingestion_root={context.roots.ingestion_root}",
            ],
        )

    fixtures_root = context.fixtures_root or DEFAULT_FIXTURES_ROOT
    responses = run_fixture_ingestion_pipeline(
        fixtures_root=fixtures_root,
        output_root=context.roots.ingestion_root,
        requested_by=context.requested_by,
        clock=context.clock,
    )
    if not responses:
        raise ValueError(f"No fixtures were discovered under `{fixtures_root}`.")

    state.outputs.fixture_refresh_and_normalization = responses
    derived_company_ids = {
        response.company.company_id
        for response in responses
        if response.company is not None
    }
    if state.resolved_company_id is None and len(derived_company_ids) == 1:
        state.resolved_company_id = next(iter(derived_company_ids))
    return StepExecutionOutcome(
        status=WorkflowStatus.SUCCEEDED,
        notes=[
            f"fixtures_root={fixtures_root}",
            f"fixtures_ingested={len(responses)}",
        ],
        child_workflow_ids=[response.ingestion_job_id for response in responses],
        child_run_summary_ids=_collect_run_summary_ids(
            [response.storage_locations for response in responses]
        ),
        produced_artifact_ids=_collect_fixture_artifact_ids(responses),
    )


def execute_evidence_extraction(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Run deterministic evidence extraction over current ingestion artifacts."""

    context = state.context
    responses = run_evidence_extraction_pipeline(
        ingestion_root=context.roots.ingestion_root,
        output_root=context.roots.parsing_root,
        requested_by=context.requested_by,
        clock=context.clock,
    )
    if not responses:
        raise ValueError(
            f"No parseable documents were discovered under `{context.roots.ingestion_root}`."
        )
    state.outputs.evidence_extraction = responses
    if state.resolved_company_id is None:
        derived_company_ids = {response.company_id for response in responses if response.company_id}
        if len(derived_company_ids) == 1:
            state.resolved_company_id = next(iter(derived_company_ids))
    return StepExecutionOutcome(
        status=WorkflowStatus.SUCCEEDED,
        notes=[f"documents_extracted={len(responses)}"],
        child_workflow_ids=[response.extraction_run_id for response in responses],
        child_run_summary_ids=_collect_run_summary_ids(
            [response.storage_locations for response in responses]
        ),
        produced_artifact_ids=_collect_evidence_artifact_ids(responses),
    )


def execute_research_workflow(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Run the deterministic research workflow for the current company slice."""

    context = state.context
    response = run_hypothesis_workflow_pipeline(
        parsing_root=context.roots.parsing_root,
        ingestion_root=context.roots.ingestion_root,
        output_root=context.roots.research_root,
        company_id=state.resolved_company_id or context.company_id,
        generate_memo_skeleton=context.generate_memo_skeleton,
        include_retrieval_context=context.include_retrieval_context,
        requested_by=context.requested_by,
        clock=context.clock,
    )
    state.outputs.research_workflow = response
    state.resolved_company_id = response.company_id
    return StepExecutionOutcome(
        status=WorkflowStatus.SUCCEEDED,
        notes=list(response.notes),
        child_workflow_ids=[response.research_workflow_id],
        child_run_summary_ids=_run_summary_ids_from_storage_locations(response.storage_locations),
        produced_artifact_ids=_collect_research_artifact_ids(response),
    )


def execute_feature_signal_pipeline(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Run feature mapping, signal generation, and signal arbitration."""

    context = state.context
    response = run_feature_signal_pipeline(
        research_root=context.roots.research_root,
        parsing_root=context.roots.parsing_root,
        output_root=context.roots.signal_root,
        company_id=state.resolved_company_id or context.company_id,
        as_of_time=context.as_of_time,
        ablation_view=context.ablation_view,
        requested_by=context.requested_by,
        clock=context.clock,
    )
    state.outputs.feature_signal_pipeline = response
    state.resolved_company_id = response.feature_mapping.company_id
    return StepExecutionOutcome(
        status=WorkflowStatus.SUCCEEDED,
        notes=[
            *response.feature_mapping.notes,
            *response.signal_generation.notes,
            *response.signal_arbitration.notes,
        ],
        child_workflow_ids=[
            response.feature_mapping.feature_mapping_run_id,
            response.signal_generation.signal_generation_run_id,
        ],
        child_run_summary_ids=_collect_run_summary_ids(
            [
                response.feature_mapping.storage_locations,
                response.signal_generation.storage_locations,
                response.signal_arbitration.storage_locations,
            ]
        ),
        produced_artifact_ids=_collect_feature_signal_artifact_ids(response),
    )


def execute_portfolio_workflow(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Run portfolio construction, attribution, stress testing, and risk review."""

    context = state.context
    response = PortfolioConstructionService(clock=context.clock).run_portfolio_workflow(
        RunPortfolioWorkflowRequest(
            signal_root=context.roots.signal_root,
            signal_arbitration_root=context.roots.signal_arbitration_root,
            research_root=context.roots.research_root,
            ingestion_root=context.roots.ingestion_root,
            backtesting_root=context.roots.backtesting_root,
            portfolio_analysis_root=context.roots.portfolio_analysis_root,
            output_root=context.roots.portfolio_root,
            company_id=state.resolved_company_id or context.company_id,
            as_of_time=context.as_of_time,
            requested_by=context.requested_by,
        )
    )
    reporting_service = ReportingService(clock=context.clock)
    validation_gates = (
        [response.validation_gate]
        if response.validation_gate is not None
        else []
    )
    risk_summary_response = reporting_service.generate_risk_summary(
        GenerateRiskSummaryRequest(
            portfolio_proposal=response.portfolio_proposal,
            risk_checks=response.risk_checks,
            stress_test_results=response.stress_test_results,
            validation_gates=validation_gates,
            requested_by=context.requested_by,
        ),
        output_root=context.roots.reporting_root,
    )
    proposal_scorecard_response = reporting_service.generate_proposal_scorecard(
        GenerateProposalScorecardRequest(
            portfolio_proposal=response.portfolio_proposal,
            portfolio_selection_summary=response.portfolio_selection_summary,
            construction_decisions=response.construction_decisions,
            position_sizing_rationales=response.position_sizing_rationales,
            portfolio_attribution=response.portfolio_attribution,
            stress_test_run=response.stress_test_run,
            stress_test_results=response.stress_test_results,
            risk_checks=response.risk_checks,
            validation_gates=validation_gates,
            paper_trades=[],
            requested_by=context.requested_by,
        ),
        output_root=context.roots.reporting_root,
    )
    updated_proposal = response.portfolio_proposal.model_copy(
        update={
            "proposal_scorecard_id": proposal_scorecard_response.proposal_scorecard.proposal_scorecard_id,
            "updated_at": context.clock.now(),
        }
    )
    portfolio_store = LocalPortfolioArtifactStore(
        root=context.roots.portfolio_root,
        clock=context.clock,
    )
    updated_proposal_storage = portfolio_store.persist_model(
        artifact_id=updated_proposal.portfolio_proposal_id,
        category="portfolio_proposals",
        model=updated_proposal,
        source_reference_ids=updated_proposal.provenance.source_reference_ids,
    )
    response = response.model_copy(
        update={
            "portfolio_proposal": updated_proposal,
            "storage_locations": [
                *response.storage_locations,
                *risk_summary_response.storage_locations,
                *proposal_scorecard_response.storage_locations,
                updated_proposal_storage,
            ],
            "notes": [
                *response.notes,
                *risk_summary_response.notes,
                *proposal_scorecard_response.notes,
                f"risk_summary_id={risk_summary_response.risk_summary.risk_summary_id}",
                (
                    "proposal_scorecard_id="
                    f"{proposal_scorecard_response.proposal_scorecard.proposal_scorecard_id}"
                ),
            ],
        }
    )
    state.outputs.portfolio_workflow = response
    state.outputs.risk_summary = risk_summary_response.risk_summary
    state.outputs.proposal_scorecard = proposal_scorecard_response.proposal_scorecard
    state.resolved_company_id = response.company_id
    return StepExecutionOutcome(
        status=WorkflowStatus.SUCCEEDED,
        notes=list(response.notes),
        child_workflow_ids=[response.portfolio_workflow_id],
        child_run_summary_ids=[],
        produced_artifact_ids=[
            *_collect_portfolio_artifact_ids(response),
            risk_summary_response.risk_summary.risk_summary_id,
            proposal_scorecard_response.proposal_scorecard.proposal_scorecard_id,
        ],
    )


def execute_review_queue_sync(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Refresh the operator review queue from current artifacts."""

    context = state.context
    response = OperatorReviewService(clock=context.clock).sync_review_queue(
        SyncReviewQueueRequest(
            research_root=context.roots.research_root,
            signal_root=context.roots.signal_root,
            portfolio_root=context.roots.portfolio_root,
            review_root=context.roots.review_root,
            audit_root=context.roots.audit_root,
        )
    )
    state.outputs.review_queue_sync = response
    return StepExecutionOutcome(
        status=WorkflowStatus.SUCCEEDED,
        notes=list(response.notes),
        produced_artifact_ids=[item.review_queue_item_id for item in response.queue_items],
    )


def execute_paper_trade_candidate_generation(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Attempt paper-trade candidate creation while preserving the review gate."""

    context = state.context
    if state.outputs.portfolio_workflow is None:
        raise ValueError("portfolio_workflow output is required before proposing paper trades.")
    proposal = state.outputs.portfolio_workflow.portfolio_proposal
    response = PaperExecutionService(clock=context.clock).propose_trades(
        PaperTradeProposalRequest(
            portfolio_proposal=proposal,
            assumed_reference_prices=context.assumed_reference_prices,
            requested_by=context.requested_by,
        ),
        output_root=context.roots.data_quality_root,
    )
    state.outputs.paper_trade_candidate_generation = response
    gate_artifact_ids = (
        [response.validation_gate.validation_gate_id]
        if response.validation_gate is not None
        else []
    )
    if response.proposed_trades:
        return StepExecutionOutcome(
            status=WorkflowStatus.SUCCEEDED,
            notes=list(response.notes),
            produced_artifact_ids=[
                *[trade.paper_trade_id for trade in response.proposed_trades],
                *gate_artifact_ids,
            ],
        )
    base_notes = [
        *response.notes,
        *(
            [f"quality_decision={response.quality_decision.value}"]
            if response.quality_decision is not None
            else []
        ),
        *(
            [f"refusal_reason={response.refusal_reason.value}"]
            if response.refusal_reason is not None
            else []
        ),
        *[f"validation_gate_id={artifact_id}" for artifact_id in gate_artifact_ids],
    ]
    is_review_bound_stop = (
        proposal.status is not PortfolioProposalStatus.APPROVED
        and not proposal.blocking_issues
        and not any(check.blocking for check in proposal.risk_checks)
        and response.refusal_reason is RefusalReason.INVALID_REVIEW_STATE
    )
    if is_review_bound_stop:
        return StepExecutionOutcome(
            status=WorkflowStatus.ATTENTION_REQUIRED,
            notes=[
                *base_notes,
                "Paper-trade candidate generation stopped intentionally at the review-bound approval gate.",
            ],
            produced_artifact_ids=gate_artifact_ids,
            manual_intervention_requirement=ManualInterventionRequirement(
                gate_reason=(
                    "Review-bound stop: portfolio proposal requires explicit human approval "
                    "before paper-trade creation."
                ),
                blocking=True,
                required_role="portfolio_reviewer",
                related_artifact_ids=[
                    proposal.portfolio_proposal_id,
                    *gate_artifact_ids,
                ],
                operator_instructions=[
                    "Review the portfolio proposal, attribution, stress results, and risk checks.",
                    "Apply an explicit portfolio review decision before requesting paper-trade candidates again.",
                ],
            ),
        )
    blocked_reason = (
        "Paper-trade candidate creation is blocked by hard proposal, risk, or validation conditions."
    )
    if response.quality_decision in {QualityDecision.REFUSE, QualityDecision.QUARANTINE}:
        blocked_reason = (
            "Paper-trade candidate creation is blocked by the current validation gate or policy state."
        )
    return StepExecutionOutcome(
        status=WorkflowStatus.ATTENTION_REQUIRED,
        notes=[
            *base_notes,
            "Paper-trade candidate generation stopped in a blocked state, not the normal review-bound stop.",
        ],
        produced_artifact_ids=gate_artifact_ids,
        manual_intervention_requirement=ManualInterventionRequirement(
            gate_reason=f"Blocked stop: {blocked_reason}",
            blocking=True,
            required_role="portfolio_reviewer",
            related_artifact_ids=[
                proposal.portfolio_proposal_id,
                *gate_artifact_ids,
            ],
            operator_instructions=[
                "Inspect the portfolio proposal, blocking risk checks, and any linked validation gate artifacts.",
                "Resolve the blocking condition before requesting paper-trade candidates again.",
            ],
        ),
    )


def execute_operations_summary(state: DailyWorkflowState) -> StepExecutionOutcome:
    """Collect health checks and recent run summaries after the daily run."""

    context = state.context
    monitoring_service = MonitoringService(clock=context.clock)
    health_checks = monitoring_service.run_health_checks(
        RunHealthChecksRequest(
            artifact_root=context.roots.artifact_root,
            monitoring_root=context.roots.monitoring_root,
            review_root=context.roots.review_root,
            limit_recent_runs=10,
        )
    )
    recent_run_summaries = monitoring_service.list_recent_run_summaries(
        ListRecentRunSummariesRequest(
            monitoring_root=context.roots.monitoring_root,
            limit=50,
        )
    )
    state.outputs.operations_health_checks = health_checks
    state.outputs.recent_run_summaries = recent_run_summaries
    reporting_service = ReportingService(clock=context.clock)
    review_queue_summary = reporting_service.generate_review_queue_summary(
        GenerateReviewQueueSummaryRequest(
            queue_items=(
                state.outputs.review_queue_sync.queue_items
                if state.outputs.review_queue_sync is not None
                else []
            ),
            requested_by=context.requested_by,
        ),
        output_root=context.roots.reporting_root,
    ).review_queue_summary
    reporting_workspace = load_reporting_workspace(context.roots.reporting_root)
    daily_paper_summaries = load_local_models(
        context.roots.portfolio_root / "daily_paper_summaries",
        DailyPaperSummary,
    )
    review_followups = load_local_models(
        context.roots.portfolio_root / "review_followups",
        ReviewFollowup,
    )
    daily_system_report = reporting_service.generate_daily_system_report(
        GenerateDailySystemReportRequest(
            report_date=context.clock.now().date(),
            run_summaries=recent_run_summaries.items,
            alert_records=health_checks.alert_records,
            service_statuses=health_checks.service_statuses,
            review_queue_summary=review_queue_summary,
            daily_paper_summaries=daily_paper_summaries,
            review_followups=review_followups,
            proposal_scorecards=(
                [state.outputs.proposal_scorecard]
                if state.outputs.proposal_scorecard is not None
                else [
                    scorecard
                    for scorecards in reporting_workspace.proposal_scorecards_by_proposal_id.values()
                    for scorecard in scorecards[:1]
                ]
            ),
            experiment_scorecards=[
                scorecard
                for scorecards in reporting_workspace.experiment_scorecards_by_experiment_id.values()
                for scorecard in scorecards[:1]
            ],
            requested_by=context.requested_by,
        ),
        output_root=context.roots.reporting_root,
    ).daily_system_report
    state.outputs.daily_system_report = daily_system_report
    return StepExecutionOutcome(
        status=WorkflowStatus.SUCCEEDED,
        notes=[
            f"health_checks={len(health_checks.health_checks)}",
            f"recent_run_summaries={recent_run_summaries.total}",
            f"open_review_followups={len([f for f in review_followups if f.status is ReviewFollowupStatus.OPEN])}",
            *(
                [f"daily_system_report_id={daily_system_report.daily_system_report_id}"]
                if daily_system_report is not None
                else []
            ),
        ],
        produced_artifact_ids=[
            *[check.health_check_id for check in health_checks.health_checks],
            *(
                [review_queue_summary.review_queue_summary_id]
                if review_queue_summary is not None
                else []
            ),
            *(
                [state.outputs.proposal_scorecard.proposal_scorecard_id]
                if state.outputs.proposal_scorecard is not None
                else []
            ),
            *( [daily_system_report.daily_system_report_id] if daily_system_report is not None else [] ),
        ],
    )


def build_executor_registry() -> dict[str, Callable[[DailyWorkflowState], StepExecutionOutcome]]:
    """Return the code-owned executor registry for the daily workflow."""

    return {
        "fixture_refresh_and_normalization": execute_fixture_refresh_and_normalization,
        "evidence_extraction": execute_evidence_extraction,
        "research_workflow": execute_research_workflow,
        "feature_signal_pipeline": execute_feature_signal_pipeline,
        "portfolio_workflow": execute_portfolio_workflow,
        "review_queue_sync": execute_review_queue_sync,
        "paper_trade_candidate_generation": execute_paper_trade_candidate_generation,
        "operations_summary": execute_operations_summary,
    }


def build_workflow_roots(*, artifact_root: Path) -> WorkflowRoots:
    """Resolve the standard artifact roots for one daily workflow run."""

    workspace = resolve_artifact_workspace(workspace_root=artifact_root)
    return WorkflowRoots(
        artifact_root=workspace.root,
        ingestion_root=workspace.ingestion_root,
        parsing_root=workspace.parsing_root,
        research_root=workspace.research_root,
        signal_root=workspace.signal_root,
        signal_arbitration_root=workspace.signal_arbitration_root,
        portfolio_root=workspace.portfolio_root,
        portfolio_analysis_root=workspace.portfolio_analysis_root,
        review_root=workspace.review_root,
        audit_root=workspace.audit_root,
        monitoring_root=workspace.monitoring_root,
        data_quality_root=workspace.data_quality_root,
        orchestration_root=workspace.orchestration_root,
        backtesting_root=workspace.backtesting_root,
        reporting_root=workspace.reporting_root,
    )


def build_daily_workflow_context(
    *,
    artifact_root: Path,
    fixtures_root: Path | None,
    data_refresh_mode: DataRefreshMode,
    company_id: str | None,
    as_of_time: datetime | None,
    generate_memo_skeleton: bool,
    include_retrieval_context: bool,
    ablation_view: AblationView,
    assumed_reference_prices: dict[str, float],
    requested_by: str,
    clock: Clock,
) -> DailyWorkflowContext:
    """Build the executor context for one orchestration run."""

    return DailyWorkflowContext(
        artifact_root=artifact_root,
        fixtures_root=fixtures_root,
        data_refresh_mode=data_refresh_mode,
        company_id=company_id,
        as_of_time=as_of_time,
        generate_memo_skeleton=generate_memo_skeleton,
        include_retrieval_context=include_retrieval_context,
        ablation_view=ablation_view,
        assumed_reference_prices=assumed_reference_prices,
        requested_by=requested_by,
        roots=build_workflow_roots(artifact_root=artifact_root),
        clock=clock,
    )


def _collect_fixture_artifact_ids(
    responses: list[FixtureIngestionResponse],
) -> list[str]:
    artifact_ids: list[str] = []
    for response in responses:
        artifact_ids.append(response.source_reference.source_reference_id)
        if response.company is not None:
            artifact_ids.append(response.company.company_id)
        if response.filing is not None:
            artifact_ids.append(response.filing.document_id)
        if response.earnings_call is not None:
            artifact_ids.append(response.earnings_call.document_id)
        if response.news_item is not None:
            artifact_ids.append(response.news_item.document_id)
        if response.price_series_metadata is not None:
            artifact_ids.append(response.price_series_metadata.price_series_metadata_id)
    return _dedupe(artifact_ids)


def _collect_evidence_artifact_ids(
    responses: list[ExtractDocumentEvidenceResponse],
) -> list[str]:
    artifact_ids: list[str] = []
    for response in responses:
        artifact_ids.append(response.document_id)
        artifact_ids.append(response.parsed_document_text.parsed_document_text_id)
        artifact_ids.extend(span.evidence_span_id for span in response.evidence_spans)
        artifact_ids.extend(claim.extracted_claim_id for claim in response.claims)
        artifact_ids.extend(risk.risk_factor_id for risk in response.risk_factors)
        artifact_ids.extend(change.guidance_change_id for change in response.guidance_changes)
        artifact_ids.extend(marker.tone_marker_id for marker in response.tone_markers)
    return _dedupe(artifact_ids)


def _collect_research_artifact_ids(response: RunResearchWorkflowResponse) -> list[str]:
    artifact_ids = [response.evidence_assessment.evidence_assessment_id]
    if response.hypothesis is not None:
        artifact_ids.append(response.hypothesis.hypothesis_id)
    if response.counter_hypothesis is not None:
        artifact_ids.append(response.counter_hypothesis.counter_hypothesis_id)
    if response.research_brief is not None:
        artifact_ids.append(response.research_brief.research_brief_id)
    if response.memo is not None:
        artifact_ids.append(response.memo.memo_id)
    artifact_ids.extend(run.agent_run_id for run in response.agent_runs)
    return _dedupe(artifact_ids)


def _collect_feature_signal_artifact_ids(response: FeatureSignalPipelineResponse) -> list[str]:
    artifact_ids: list[str] = []
    artifact_ids.extend(
        definition.feature_definition_id for definition in response.feature_mapping.feature_definitions
    )
    artifact_ids.extend(value.feature_value_id for value in response.feature_mapping.feature_values)
    artifact_ids.extend(feature.feature_id for feature in response.feature_mapping.features)
    artifact_ids.extend(score.signal_score_id for score in response.signal_generation.signal_scores)
    artifact_ids.extend(signal.signal_id for signal in response.signal_generation.signals)
    artifact_ids.extend(
        calibration.signal_calibration_id
        for calibration in response.signal_arbitration.signal_calibrations
    )
    artifact_ids.extend(
        conflict.signal_conflict_id for conflict in response.signal_arbitration.signal_conflicts
    )
    if response.signal_arbitration.signal_bundle is not None:
        artifact_ids.append(response.signal_arbitration.signal_bundle.signal_bundle_id)
    if response.signal_arbitration.arbitration_decision is not None:
        artifact_ids.append(response.signal_arbitration.arbitration_decision.arbitration_decision_id)
    return _dedupe(artifact_ids)


def _collect_portfolio_artifact_ids(response: RunPortfolioWorkflowResponse) -> list[str]:
    artifact_ids: list[str] = [
        *[idea.position_idea_id for idea in response.position_ideas],
        response.portfolio_proposal.portfolio_proposal_id,
        *[check.risk_check_id for check in response.risk_checks],
        *[attribution.position_attribution_id for attribution in response.position_attributions],
        *[definition.scenario_definition_id for definition in response.scenario_definitions],
        *[result.stress_test_result_id for result in response.stress_test_results],
    ]
    if response.portfolio_attribution is not None:
        artifact_ids.append(response.portfolio_attribution.portfolio_attribution_id)
    if response.stress_test_run is not None:
        artifact_ids.append(response.stress_test_run.stress_test_run_id)
    return _dedupe(artifact_ids)


def _collect_run_summary_ids(
    storage_location_groups: list[list[ArtifactStorageLocation]]
    | tuple[list[ArtifactStorageLocation], ...],
) -> list[str]:
    run_summary_ids: list[str] = []
    for group in storage_location_groups:
        run_summary_ids.extend(_run_summary_ids_from_storage_locations(group))
    return _dedupe(run_summary_ids)


def _run_summary_ids_from_storage_locations(
    storage_locations: list[ArtifactStorageLocation],
) -> list[str]:
    return _dedupe(
        [
            storage_location.artifact_id
            for storage_location in storage_locations
            if storage_location.artifact_id.startswith("runsum_")
        ]
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def make_step_id(*, workflow_execution_id: str, step_name: str) -> str:
    """Build a deterministic run-step identifier."""

    return make_canonical_id("rstep", workflow_execution_id, step_name)
