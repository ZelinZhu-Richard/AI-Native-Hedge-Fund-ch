from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.core import build_provenance, resolve_artifact_workspace
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AblationView,
    ArtifactStorageLocation,
    DailySystemReport,
    DataRefreshMode,
    ManualInterventionRequirement,
    PipelineEventType,
    ProposalScorecard,
    RiskSummary,
    RunbookEntry,
    RunFailureAction,
    RunStep,
    ScheduledRunConfig,
    ScheduleMode,
    StrictModel,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
)
from libraries.utils import make_canonical_id, make_prefixed_id
from pipelines.signal_generation.feature_signal_pipeline import FeatureSignalPipelineResponse
from services.daily_orchestration.definitions import (
    DAILY_WORKFLOW_NAME,
    build_runbook_entries,
    build_workflow_definition,
    get_step_specs,
)
from services.daily_orchestration.executors import (
    DailyWorkflowState,
    StepExecutionOutcome,
    build_daily_workflow_context,
    build_executor_registry,
    make_step_id,
)
from services.daily_orchestration.storage import LocalOrchestrationArtifactStore
from services.ingestion import FixtureIngestionResponse
from services.monitoring import (
    ListRecentRunSummariesResponse,
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
    RunHealthChecksResponse,
)
from services.operator_review import SyncReviewQueueResponse
from services.paper_execution import PaperTradeProposalResponse
from services.parsing import ExtractDocumentEvidenceResponse
from services.portfolio import RunPortfolioWorkflowResponse
from services.research_orchestrator import RunResearchWorkflowResponse


class RunDailyWorkflowRequest(StrictModel):
    """Explicit local request to run the deterministic daily operating workflow."""

    artifact_root: Path = Field(description="Base artifact root for the isolated daily run.")
    fixtures_root: Path | None = Field(
        default=None,
        description="Optional fixture root for local refresh mode.",
    )
    data_refresh_mode: DataRefreshMode = Field(
        default=DataRefreshMode.FIXTURE_REFRESH,
        description="Whether to refresh local fixtures or reuse existing ingestion artifacts.",
    )
    company_id: str | None = Field(
        default=None,
        description="Optional company slice when the artifact roots contain multiple companies.",
    )
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional point-in-time boundary for research, signal, and portfolio steps.",
    )
    generate_memo_skeleton: bool = Field(
        default=True,
        description="Whether the research workflow should generate a memo skeleton.",
    )
    include_retrieval_context: bool = Field(
        default=True,
        description="Whether the research workflow should retrieve same-company prior work.",
    )
    ablation_view: AblationView = Field(
        default=AblationView.TEXT_ONLY,
        description="Signal-view slice used by the feature and signal pipeline.",
    )
    assumed_reference_prices: dict[str, float] = Field(
        default_factory=dict,
        description="Optional prices used when materializing paper-trade candidate quantities.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunDailyWorkflowResponse(StrictModel):
    """Typed result of one deterministic local daily workflow run."""

    workflow_definition: WorkflowDefinition = Field(
        description="Code-owned definition used for the daily run."
    )
    scheduled_run_config: ScheduledRunConfig = Field(
        description="Persisted local run configuration for the workflow."
    )
    workflow_execution: WorkflowExecution = Field(
        description="Top-level persisted execution record for the daily run."
    )
    run_steps: list[RunStep] = Field(
        default_factory=list,
        description="Inspectable execution records for each workflow step.",
    )
    runbook_entries: list[RunbookEntry] = Field(
        default_factory=list,
        description="Persisted operator runbook entries generated from the step registry.",
    )
    fixture_refresh_and_normalization: list[FixtureIngestionResponse] = Field(
        default_factory=list,
        description="Fixture-ingestion responses when fixture refresh executed.",
    )
    evidence_extraction: list[ExtractDocumentEvidenceResponse] = Field(
        default_factory=list,
        description="Evidence-extraction responses for the current run.",
    )
    research_workflow: RunResearchWorkflowResponse | None = Field(
        default=None,
        description="Research workflow response when the step ran.",
    )
    feature_signal_pipeline: FeatureSignalPipelineResponse | None = Field(
        default=None,
        description="Feature and signal pipeline response when the step ran.",
    )
    portfolio_workflow: RunPortfolioWorkflowResponse | None = Field(
        default=None,
        description="Portfolio workflow response when the step ran.",
    )
    risk_summary: RiskSummary | None = Field(
        default=None,
        description="Grounded risk summary generated from the daily proposal when available.",
    )
    proposal_scorecard: ProposalScorecard | None = Field(
        default=None,
        description="Grounded proposal scorecard generated from the daily proposal when available.",
    )
    review_queue_sync: SyncReviewQueueResponse | None = Field(
        default=None,
        description="Review queue sync response when the step ran.",
    )
    paper_trade_candidate_generation: PaperTradeProposalResponse | None = Field(
        default=None,
        description="Paper-trade candidate response when the step ran.",
    )
    operations_health_checks: RunHealthChecksResponse | None = Field(
        default=None,
        description="Monitoring health-check response when the operations summary step ran.",
    )
    recent_run_summaries: ListRecentRunSummariesResponse | None = Field(
        default=None,
        description="Recent run-summary listing captured by the operations summary step.",
    )
    daily_system_report: DailySystemReport | None = Field(
        default=None,
        description="Grounded daily system report generated from monitoring and review outputs.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Storage locations written by the orchestration layer itself.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Workflow-level notes including manual stops or failure handling.",
    )


class DailyOrchestrationService(BaseService):
    """Run the deterministic local daily operating workflow and persist inspectable state."""

    capability_name = "daily_orchestration"
    capability_description = (
        "Runs the local daily research-to-review operating workflow with explicit step state and runbook artifacts."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=[
                "fixture roots",
                "persisted artifact roots",
                "existing workflow services",
            ],
            produces=[
                "WorkflowDefinition",
                "ScheduledRunConfig",
                "WorkflowExecution",
                "RunStep",
                "RunbookEntry",
            ],
            api_routes=[],
        )

    def run_daily_workflow(self, request: RunDailyWorkflowRequest) -> RunDailyWorkflowResponse:
        """Execute the deterministic local daily operating workflow."""

        workflow_execution_id = make_prefixed_id("dwflow")
        context = build_daily_workflow_context(
            artifact_root=request.artifact_root,
            fixtures_root=request.fixtures_root,
            data_refresh_mode=request.data_refresh_mode,
            company_id=request.company_id,
            as_of_time=request.as_of_time,
            generate_memo_skeleton=request.generate_memo_skeleton,
            include_retrieval_context=request.include_retrieval_context,
            ablation_view=request.ablation_view,
            assumed_reference_prices=request.assumed_reference_prices,
            requested_by=request.requested_by,
            clock=self.clock,
        )
        orchestration_root = context.roots.orchestration_root
        monitoring_root = context.roots.monitoring_root
        store = LocalOrchestrationArtifactStore(root=orchestration_root, clock=self.clock)
        monitoring_service = MonitoringService(clock=self.clock)
        executor_registry = build_executor_registry()
        step_specs = get_step_specs()
        started_at = self.clock.now()

        workflow_definition = build_workflow_definition(clock=self.clock)
        scheduled_run_config = self._build_scheduled_run_config(
            request=request,
            workflow_definition=workflow_definition,
        )
        runbook_entries = build_runbook_entries(clock=self.clock)
        run_steps = self._build_run_steps(
            workflow_execution_id=workflow_execution_id,
            workflow_definition=workflow_definition,
        )
        workflow_execution = WorkflowExecution(
            workflow_execution_id=workflow_execution_id,
            workflow_definition_id=workflow_definition.workflow_definition_id,
            scheduled_run_config_id=scheduled_run_config.scheduled_run_config_id,
            status=WorkflowStatus.RUNNING,
            step_ids=[step.run_step_id for step in run_steps],
            linked_child_run_summary_ids=[],
            produced_artifact_ids=[],
            started_at=started_at,
            completed_at=None,
            notes=[
                f"requested_by={request.requested_by}",
                f"data_refresh_mode={request.data_refresh_mode.value}",
                f"artifact_root={request.artifact_root}",
            ],
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="daily_orchestration_workflow_execution",
                upstream_artifact_ids=[
                    workflow_definition.workflow_definition_id,
                    scheduled_run_config.scheduled_run_config_id,
                ],
                workflow_run_id=workflow_execution_id,
                notes=[f"requested_by={request.requested_by}"],
            ),
            created_at=started_at,
            updated_at=started_at,
        )

        storage_locations: list[ArtifactStorageLocation] = []
        storage_locations.extend(self._persist_static_artifacts(store, workflow_definition, scheduled_run_config))
        for runbook_entry in runbook_entries:
            storage_locations.append(
                store.persist_model(
                    artifact_id=runbook_entry.runbook_entry_id,
                    category="runbook_entries",
                    model=runbook_entry,
                    source_reference_ids=[],
                )
            )
        storage_locations.append(self._persist_execution(store, workflow_execution))
        for step in run_steps:
            storage_locations.append(self._persist_step(store, step))

        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name=DAILY_WORKFLOW_NAME,
                workflow_run_id=workflow_execution_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message="Daily workflow started.",
                related_artifact_ids=[workflow_execution_id],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )

        state = DailyWorkflowState(
            context=context,
            resolved_company_id=request.company_id,
        )
        steps_by_name = {step.step_name: step for step in run_steps}
        child_run_summary_ids: list[str] = []
        produced_artifact_ids: list[str] = []
        workflow_notes = list(workflow_execution.notes)
        workflow_status: WorkflowStatus | None = None
        failure_messages: list[str] = []
        attention_reasons: list[str] = []
        final_event_type = PipelineEventType.RUN_COMPLETED

        for spec in step_specs:
            step = steps_by_name[spec.step_name]
            step = step.model_copy(
                update={
                    "status": WorkflowStatus.RUNNING,
                    "started_at": self.clock.now(),
                    "updated_at": self.clock.now(),
                }
            )
            steps_by_name[spec.step_name] = step
            self._persist_step(store, step)
            outcome: StepExecutionOutcome | None = None
            step_error: Exception | None = None

            for attempt_index in range(1, spec.retry_policy.max_attempts + 1):
                try:
                    outcome = executor_registry[spec.step_name](state)
                    step = step.model_copy(
                        update={
                            "status": outcome.status,
                            "attempt_count": attempt_index,
                            "child_workflow_ids": outcome.child_workflow_ids,
                            "child_run_summary_ids": outcome.child_run_summary_ids,
                            "produced_artifact_ids": outcome.produced_artifact_ids,
                            "notes": [*step.notes, *outcome.notes],
                            "manual_intervention_requirement": outcome.manual_intervention_requirement,
                            "completed_at": self.clock.now(),
                            "updated_at": self.clock.now(),
                        }
                    )
                    steps_by_name[spec.step_name] = step
                    self._persist_step(store, step)
                    child_run_summary_ids = _dedupe(
                        [*child_run_summary_ids, *outcome.child_run_summary_ids]
                    )
                    produced_artifact_ids = _dedupe(
                        [*produced_artifact_ids, *outcome.produced_artifact_ids]
                    )
                    workflow_notes.extend(
                        [f"{spec.step_name}:{note}" for note in outcome.notes]
                    )
                    workflow_execution = workflow_execution.model_copy(
                        update={
                            "linked_child_run_summary_ids": child_run_summary_ids,
                            "produced_artifact_ids": produced_artifact_ids,
                            "notes": workflow_notes,
                            "updated_at": self.clock.now(),
                        }
                    )
                    self._persist_execution(store, workflow_execution)
                    if outcome.status is WorkflowStatus.ATTENTION_REQUIRED:
                        attention_reasons.append(
                            outcome.manual_intervention_requirement.gate_reason
                            if outcome.manual_intervention_requirement is not None
                            else f"Step `{spec.step_name}` requires operator attention."
                        )
                        if outcome.stop_workflow:
                            workflow_status = WorkflowStatus.ATTENTION_REQUIRED
                    break
                except Exception as exc:  # noqa: BLE001
                    step_error = exc
                    if spec.retry_policy.automatic_retry_enabled and attempt_index < spec.retry_policy.max_attempts:
                        retry_note = (
                            f"Attempt {attempt_index} failed with `{exc}`. Retrying step `{spec.step_name}`."
                        )
                        step = step.model_copy(
                            update={
                                "attempt_count": attempt_index,
                                "notes": [*step.notes, retry_note],
                                "updated_at": self.clock.now(),
                            }
                        )
                        steps_by_name[spec.step_name] = step
                        self._persist_step(store, step)
                        continue
                    failure_message = f"Step `{spec.step_name}` failed: {exc}"
                    failure_messages.append(failure_message)
                    workflow_notes.append(failure_message)
                    if spec.failure_action is RunFailureAction.FAIL_WORKFLOW:
                        step_status = WorkflowStatus.FAILED
                        workflow_status = WorkflowStatus.FAILED
                        final_event_type = PipelineEventType.RUN_FAILED
                    elif spec.failure_action is RunFailureAction.ATTENTION_REQUIRED_STOP:
                        step_status = WorkflowStatus.ATTENTION_REQUIRED
                        workflow_status = WorkflowStatus.ATTENTION_REQUIRED
                        final_event_type = PipelineEventType.ATTENTION_REQUIRED
                        attention_reasons.append(
                            f"Step `{spec.step_name}` failed and needs operator attention."
                        )
                    else:
                        step_status = WorkflowStatus.FAILED
                        workflow_status = WorkflowStatus.PARTIAL
                        final_event_type = PipelineEventType.RUN_COMPLETED
                    step = step.model_copy(
                        update={
                            "status": step_status,
                            "attempt_count": attempt_index,
                            "notes": [*step.notes, failure_message],
                            "manual_intervention_requirement": (
                                _build_failure_intervention_requirement(
                                    step_name=spec.step_name,
                                    failure_message=failure_message,
                                )
                                if spec.failure_action is RunFailureAction.ATTENTION_REQUIRED_STOP
                                else step.manual_intervention_requirement
                            ),
                            "completed_at": self.clock.now(),
                            "updated_at": self.clock.now(),
                        }
                    )
                    steps_by_name[spec.step_name] = step
                    self._persist_step(store, step)
                    workflow_execution = workflow_execution.model_copy(
                        update={
                            "notes": workflow_notes,
                            "updated_at": self.clock.now(),
                        }
                    )
                    self._persist_execution(store, workflow_execution)
                    break

            if workflow_status in {
                WorkflowStatus.FAILED,
                WorkflowStatus.PARTIAL,
                WorkflowStatus.ATTENTION_REQUIRED,
            }:
                if outcome is None or outcome.stop_workflow or step_error is not None:
                    break

        if workflow_status is None:
            if attention_reasons:
                workflow_status = WorkflowStatus.ATTENTION_REQUIRED
                final_event_type = PipelineEventType.ATTENTION_REQUIRED
            else:
                workflow_status = WorkflowStatus.SUCCEEDED
                final_event_type = PipelineEventType.RUN_COMPLETED

        completed_at = self.clock.now()
        workflow_execution = workflow_execution.model_copy(
            update={
                "status": workflow_status,
                "linked_child_run_summary_ids": child_run_summary_ids,
                "produced_artifact_ids": produced_artifact_ids,
                "completed_at": completed_at,
                "notes": workflow_notes,
                "updated_at": completed_at,
            }
        )
        self._persist_execution(store, workflow_execution)
        run_steps = [steps_by_name[spec.step_name] for spec in step_specs]

        final_message = _final_message_for_status(workflow_status)
        completed_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name=DAILY_WORKFLOW_NAME,
                workflow_run_id=workflow_execution_id,
                service_name=self.capability_name,
                event_type=final_event_type,
                status=workflow_status,
                message=final_message,
                related_artifact_ids=[workflow_execution_id, *produced_artifact_ids],
                notes=workflow_notes,
            ),
            output_root=monitoring_root,
        )
        summary_response = monitoring_service.record_run_summary(
            RecordRunSummaryRequest(
                workflow_name=DAILY_WORKFLOW_NAME,
                workflow_run_id=workflow_execution_id,
                service_name=self.capability_name,
                requested_by=request.requested_by,
                status=workflow_status,
                started_at=started_at,
                completed_at=completed_at,
                storage_locations=storage_locations,
                produced_artifact_ids=[
                    workflow_execution.workflow_execution_id,
                    *workflow_execution.produced_artifact_ids,
                ],
                produced_artifact_counts={
                    "run_steps": len(run_steps),
                    "runbook_entries": len(runbook_entries),
                },
                pipeline_event_ids=[
                    start_event.pipeline_event.pipeline_event_id,
                    completed_event.pipeline_event.pipeline_event_id,
                ],
                failure_messages=failure_messages,
                attention_reasons=attention_reasons,
                notes=workflow_notes,
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        storage_locations.extend(
            [
                start_event.storage_location,
                completed_event.storage_location,
                *summary_response.storage_locations,
            ]
        )

        return RunDailyWorkflowResponse(
            workflow_definition=workflow_definition,
            scheduled_run_config=scheduled_run_config,
            workflow_execution=workflow_execution,
            run_steps=run_steps,
            runbook_entries=runbook_entries,
            fixture_refresh_and_normalization=state.outputs.fixture_refresh_and_normalization,
            evidence_extraction=state.outputs.evidence_extraction,
            research_workflow=state.outputs.research_workflow,
            feature_signal_pipeline=state.outputs.feature_signal_pipeline,
            portfolio_workflow=state.outputs.portfolio_workflow,
            risk_summary=state.outputs.risk_summary,
            proposal_scorecard=state.outputs.proposal_scorecard,
            review_queue_sync=state.outputs.review_queue_sync,
            paper_trade_candidate_generation=state.outputs.paper_trade_candidate_generation,
            operations_health_checks=state.outputs.operations_health_checks,
            recent_run_summaries=state.outputs.recent_run_summaries,
            daily_system_report=state.outputs.daily_system_report,
            storage_locations=storage_locations,
            notes=workflow_notes,
        )

    def _build_scheduled_run_config(
        self,
        *,
        request: RunDailyWorkflowRequest,
        workflow_definition: WorkflowDefinition,
    ) -> ScheduledRunConfig:
        """Build the persisted local scheduled-run configuration."""

        now = self.clock.now()
        workspace = resolve_artifact_workspace(workspace_root=request.artifact_root)
        artifact_roots = {
            "artifact_root": workspace.root,
            "ingestion_root": workspace.ingestion_root,
            "parsing_root": workspace.parsing_root,
            "research_root": workspace.research_root,
            "signal_root": workspace.signal_root,
            "signal_arbitration_root": workspace.signal_arbitration_root,
            "portfolio_root": workspace.portfolio_root,
            "portfolio_analysis_root": workspace.portfolio_analysis_root,
            "review_root": workspace.review_root,
            "monitoring_root": workspace.monitoring_root,
            "orchestration_root": workspace.orchestration_root,
            "reporting_root": workspace.reporting_root,
        }
        schedule_mode = ScheduleMode.MANUAL_LOCAL
        config_id = make_canonical_id(
            "srcfg",
            workflow_definition.workflow_definition_id,
            schedule_mode.value,
            str(request.artifact_root),
            request.data_refresh_mode.value,
            request.company_id or "all_companies",
        )
        return ScheduledRunConfig(
            scheduled_run_config_id=config_id,
            workflow_definition_id=workflow_definition.workflow_definition_id,
            schedule_mode=schedule_mode,
            enabled=True,
            artifact_roots=artifact_roots,
            default_requester=request.requested_by,
            data_refresh_mode=request.data_refresh_mode,
            company_id=request.company_id,
            fixtures_root=request.fixtures_root,
            ablation_view=request.ablation_view,
            assumed_reference_prices=request.assumed_reference_prices,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="daily_orchestration_scheduled_run_config",
                upstream_artifact_ids=[workflow_definition.workflow_definition_id],
                notes=[f"artifact_root={request.artifact_root}"],
            ),
            created_at=now,
            updated_at=now,
        )

    def _build_run_steps(
        self,
        *,
        workflow_execution_id: str,
        workflow_definition: WorkflowDefinition,
    ) -> list[RunStep]:
        """Build queued run-step records from the code-owned workflow definition."""

        now = self.clock.now()
        step_ids = {
            definition.step_name: make_step_id(
                workflow_execution_id=workflow_execution_id,
                step_name=definition.step_name,
            )
            for definition in workflow_definition.step_definitions
        }
        return [
            RunStep(
                run_step_id=step_ids[definition.step_name],
                workflow_execution_id=workflow_execution_id,
                step_name=definition.step_name,
                sequence_index=definition.sequence_index,
                dependency_step_ids=[
                    step_ids[dependency_name]
                    for dependency_name in definition.dependency_step_names
                ],
                owning_service=definition.owning_service,
                status=WorkflowStatus.QUEUED,
                attempt_count=0,
                retry_policy=definition.retry_policy,
                failure_action=definition.failure_action,
                child_workflow_ids=[],
                child_run_summary_ids=[],
                produced_artifact_ids=[],
                notes=[],
                manual_intervention_requirement=None,
                started_at=None,
                completed_at=None,
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="daily_orchestration_run_step",
                    upstream_artifact_ids=[
                        workflow_execution_id,
                        *[
                            step_ids[dependency_name]
                            for dependency_name in definition.dependency_step_names
                        ],
                    ],
                    workflow_run_id=workflow_execution_id,
                ),
                created_at=now,
                updated_at=now,
            )
            for definition in workflow_definition.step_definitions
        ]

    def _persist_static_artifacts(
        self,
        store: LocalOrchestrationArtifactStore,
        workflow_definition: WorkflowDefinition,
        scheduled_run_config: ScheduledRunConfig,
    ) -> list[ArtifactStorageLocation]:
        """Persist workflow-definition and scheduled-run artifacts."""

        return [
            store.persist_model(
                artifact_id=workflow_definition.workflow_definition_id,
                category="workflow_definitions",
                model=workflow_definition,
                source_reference_ids=[],
            ),
            store.persist_model(
                artifact_id=scheduled_run_config.scheduled_run_config_id,
                category="scheduled_run_configs",
                model=scheduled_run_config,
                source_reference_ids=[],
            ),
        ]

    def _persist_execution(
        self,
        store: LocalOrchestrationArtifactStore,
        execution: WorkflowExecution,
    ) -> ArtifactStorageLocation:
        """Persist the current workflow execution snapshot."""

        return store.persist_model(
            artifact_id=execution.workflow_execution_id,
            category="workflow_executions",
            model=execution,
            source_reference_ids=[],
        )

    def _persist_step(
        self,
        store: LocalOrchestrationArtifactStore,
        step: RunStep,
    ) -> ArtifactStorageLocation:
        """Persist one run-step snapshot."""

        return store.persist_model(
            artifact_id=step.run_step_id,
            category="run_steps",
            model=step,
            source_reference_ids=[],
        )


def _build_failure_intervention_requirement(
    *,
    step_name: str,
    failure_message: str,
) -> ManualInterventionRequirement:
    return ManualInterventionRequirement(
        gate_reason=f"Step `{step_name}` failed and requires operator attention.",
        blocking=True,
        required_role="operator",
        related_artifact_ids=[],
        operator_instructions=[
            "Inspect the daily orchestration step notes and linked child run summaries.",
            "Fix the underlying issue before rerunning the daily workflow.",
        ],
    )


def _final_message_for_status(status: WorkflowStatus) -> str:
    if status is WorkflowStatus.SUCCEEDED:
        return "Daily workflow completed successfully."
    if status is WorkflowStatus.ATTENTION_REQUIRED:
        return "Daily workflow completed but requires explicit operator attention."
    if status is WorkflowStatus.PARTIAL:
        return "Daily workflow completed core steps but finished in a partial state."
    return "Daily workflow failed."


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
