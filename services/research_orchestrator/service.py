from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AgentRun,
    AgentRunStatus,
    ArtifactStorageLocation,
    AuditOutcome,
    CounterHypothesis,
    EvidenceAssessment,
    EvidenceGrade,
    Hypothesis,
    Memo,
    MemoryScope,
    PipelineEventType,
    ResearchBrief,
    RetrievalContext,
    RetrievalQuery,
    StrictModel,
    WorkflowStatus,
)
from libraries.utils import make_prefixed_id
from services.audit import AuditEventRequest, AuditLoggingService
from services.memo import MemoGenerationRequest, MemoGenerationService
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.research_memory import ResearchMemoryService, SearchResearchMemoryRequest
from services.research_orchestrator.briefs import build_research_brief
from services.research_orchestrator.critique import generate_counter_hypothesis
from services.research_orchestrator.grading import build_evidence_assessment
from services.research_orchestrator.hypothesis import generate_hypothesis
from services.research_orchestrator.loaders import LoadedResearchArtifacts, load_research_artifacts
from services.research_orchestrator.storage import LocalResearchArtifactStore


class ResearchCycleRequest(StrictModel):
    """Request to launch a coordinated research cycle for a company or theme."""

    objective: str = Field(description="Research objective to pursue.")
    company_id: str | None = Field(
        default=None, description="Primary company under coverage when applicable."
    )
    trigger_type: str = Field(description="Trigger for the cycle, such as filing or news.")
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts that triggered the cycle.",
    )
    as_of_time: datetime = Field(description="UTC time defining the cycle information boundary.")
    requested_by: str = Field(description="Requester identifier.")


class ResearchCycleResponse(StrictModel):
    """Response returned after accepting a research cycle."""

    research_cycle_id: str = Field(description="Canonical research cycle identifier.")
    status: str = Field(description="Operational status.")
    started_at: datetime = Field(description="UTC timestamp when orchestration began.")
    planned_agents: list[str] = Field(
        default_factory=list,
        description="Agents planned for the cycle.",
    )


class RunResearchWorkflowRequest(StrictModel):
    """Request to execute the deterministic Day 4 research workflow."""

    parsing_root: Path = Field(description="Root path for persisted parsing artifacts.")
    ingestion_root: Path | None = Field(
        default=None,
        description="Optional root path for normalized ingestion artifacts used as context.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional research artifact root. Defaults to the configured artifact root.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when the parsing root contains multiple companies.",
    )
    generate_memo_skeleton: bool = Field(
        default=True,
        description="Whether to render a draft memo skeleton from the research brief.",
    )
    include_retrieval_context: bool = Field(
        default=True,
        description="Whether to retrieve same-company prior work as advisory context.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunResearchWorkflowResponse(StrictModel):
    """Result of the deterministic Day 4 research workflow."""

    research_workflow_id: str = Field(description="Canonical workflow execution identifier.")
    status: str = Field(description="Operational status for the workflow.")
    company_id: str = Field(description="Covered company identifier.")
    hypothesis: Hypothesis | None = Field(
        default=None,
        description="Generated hypothesis when support is sufficient.",
    )
    evidence_assessment: EvidenceAssessment = Field(
        description="Evidence assessment for the current support base."
    )
    counter_hypothesis: CounterHypothesis | None = Field(
        default=None,
        description="Generated counter-hypothesis when a primary thesis exists.",
    )
    research_brief: ResearchBrief | None = Field(
        default=None,
        description="Memo-ready research brief when a primary thesis exists.",
    )
    memo: Memo | None = Field(
        default=None,
        description="Optional draft memo skeleton rendered from the research brief.",
    )
    retrieval_context: RetrievalContext | None = Field(
        default=None,
        description="Optional advisory retrieval context used for the workflow.",
    )
    agent_runs: list[AgentRun] = Field(
        default_factory=list,
        description="Agent-run records for each research workflow step.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Workflow notes, including escalation or insufficiency reasons.",
    )


class ResearchOrchestrationService(BaseService):
    """Coordinate deterministic research workflows across evidence, critique, and memo layers."""

    capability_name = "research_orchestrator"
    capability_description = "Coordinates deterministic research workflows on top of evidence artifacts."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["parsing artifacts", "Company", "ResearchCycleRequest"],
            produces=[
                "Hypothesis",
                "EvidenceAssessment",
                "CounterHypothesis",
                "ResearchBrief",
                "Memo",
                "AgentRun",
            ],
            api_routes=[],
        )

    def start_cycle(self, request: ResearchCycleRequest) -> ResearchCycleResponse:
        """Start a new research cycle."""

        return ResearchCycleResponse(
            research_cycle_id=make_prefixed_id("cycle"),
            status="started",
            started_at=self.clock.now(),
            planned_agents=[
                "filing_ingestion_agent",
                "transcript_agent",
                "news_agent",
                "hypothesis_agent",
                "evidence_grader_agent",
                "counterargument_agent",
                "memo_writer_agent",
            ],
        )

    def run_research_workflow(
        self, request: RunResearchWorkflowRequest
    ) -> RunResearchWorkflowResponse:
        """Execute the deterministic Day 4 hypothesis and critique workflow."""

        research_workflow_id = make_prefixed_id("rflow")
        resolved_output_root = request.output_root or (get_settings().resolved_artifact_root / "research")
        audit_root = resolved_output_root.parent / "audit"
        monitoring_root = resolved_output_root.parent / "monitoring"
        monitoring_service = MonitoringService(clock=self.clock)
        started_at = self.clock.now()
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="research_workflow",
                workflow_run_id=research_workflow_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message="Research workflow started.",
                related_artifact_ids=[],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        try:
            inputs = load_research_artifacts(
                parsing_root=request.parsing_root,
                ingestion_root=request.ingestion_root,
                company_id=request.company_id,
            )
            notes = [f"requested_by={request.requested_by}"]
            retrieval_context = (
                self._build_retrieval_context(
                    request=request,
                    resolved_output_root=resolved_output_root,
                    company_id=inputs.company_id,
                    started_at=started_at,
                )
                if request.include_retrieval_context
                else None
            )
            if retrieval_context is not None:
                notes.append(
                    f"retrieval_context_results={len(retrieval_context.results) + len(retrieval_context.evidence_results)}"
                )
            agent_runs: list[AgentRun] = []
            input_artifact_ids = _input_artifact_ids(inputs)

            hypothesis_agent_run_id = make_prefixed_id("arun")
            hypothesis_result = generate_hypothesis(
                inputs=inputs,
                clock=self.clock,
                workflow_run_id=research_workflow_id,
                agent_run_id=hypothesis_agent_run_id,
            )
            notes.extend(hypothesis_result.notes)
            hypothesis = hypothesis_result.hypothesis
            agent_runs.append(
                self._build_agent_run(
                    agent_name="hypothesis_agent",
                    objective="Generate one disciplined research hypothesis from evidence artifacts.",
                    input_artifact_ids=input_artifact_ids,
                    output_artifact_ids=[hypothesis.hypothesis_id] if hypothesis is not None else [],
                    status=AgentRunStatus.SUCCEEDED if hypothesis is not None else AgentRunStatus.ESCALATED,
                    workflow_run_id=research_workflow_id,
                    agent_run_id=hypothesis_agent_run_id,
                    escalation_reason="; ".join(hypothesis_result.notes) if hypothesis is None else None,
                )
            )

            assessment_agent_run_id = make_prefixed_id("arun")
            evidence_assessment = build_evidence_assessment(
                company_id=inputs.company_id,
                hypothesis=hypothesis,
                supporting_evidence_links=hypothesis_result.supporting_evidence_links,
                generation_notes=hypothesis_result.notes,
                inputs=inputs,
                clock=self.clock,
                workflow_run_id=research_workflow_id,
                agent_run_id=assessment_agent_run_id,
            )
            agent_runs.append(
                self._build_agent_run(
                    agent_name="evidence_grader_agent",
                    objective="Assess evidence sufficiency and support gaps for the generated thesis.",
                    input_artifact_ids=input_artifact_ids,
                    output_artifact_ids=[evidence_assessment.evidence_assessment_id],
                    status=AgentRunStatus.SUCCEEDED,
                    workflow_run_id=research_workflow_id,
                    agent_run_id=assessment_agent_run_id,
                    escalation_reason=None,
                )
            )

            if hypothesis is None or evidence_assessment.grade == EvidenceGrade.INSUFFICIENT:
                storage_locations = self._persist_partial_workflow(
                    output_root=resolved_output_root,
                    inputs=inputs,
                    evidence_assessment=evidence_assessment,
                    agent_runs=agent_runs,
                )
                audit_response = AuditLoggingService(clock=self.clock).record_event(
                    AuditEventRequest(
                        event_type="research_workflow_insufficient",
                        actor_type="service",
                        actor_id="research_orchestrator",
                        target_type="research_workflow",
                        target_id=research_workflow_id,
                        action="insufficient_evidence",
                        outcome=AuditOutcome.WARNING,
                        reason="Deterministic research workflow ended without a thesis due to insufficient support.",
                        request_id=research_workflow_id,
                        related_artifact_ids=[
                            evidence_assessment.evidence_assessment_id,
                            *[agent_run.agent_run_id for agent_run in agent_runs],
                        ],
                        notes=notes,
                    ),
                    output_root=audit_root,
                )
                storage_locations.append(audit_response.storage_location)
                completed_event = monitoring_service.record_pipeline_event(
                    RecordPipelineEventRequest(
                        workflow_name="research_workflow",
                        workflow_run_id=research_workflow_id,
                        service_name=self.capability_name,
                        event_type=PipelineEventType.RUN_COMPLETED,
                        status=WorkflowStatus.SUCCEEDED,
                        message="Research workflow completed with insufficient support.",
                        related_artifact_ids=[
                            evidence_assessment.evidence_assessment_id,
                            *[agent_run.agent_run_id for agent_run in agent_runs],
                        ],
                        notes=[f"requested_by={request.requested_by}"],
                    ),
                    output_root=monitoring_root,
                )
                attention_event = monitoring_service.record_pipeline_event(
                    RecordPipelineEventRequest(
                        workflow_name="research_workflow",
                        workflow_run_id=research_workflow_id,
                        service_name=self.capability_name,
                        event_type=PipelineEventType.ATTENTION_REQUIRED,
                        status=WorkflowStatus.ATTENTION_REQUIRED,
                        message="Research workflow produced insufficient support for a thesis.",
                        related_artifact_ids=[evidence_assessment.evidence_assessment_id],
                        notes=[f"requested_by={request.requested_by}"],
                    ),
                    output_root=monitoring_root,
                )
                monitoring_service.record_run_summary(
                    RecordRunSummaryRequest(
                        workflow_name="research_workflow",
                        workflow_run_id=research_workflow_id,
                        service_name=self.capability_name,
                        requested_by=request.requested_by,
                        status=WorkflowStatus.ATTENTION_REQUIRED,
                        started_at=started_at,
                        completed_at=self.clock.now(),
                        storage_locations=storage_locations,
                        produced_artifact_ids=[
                            evidence_assessment.evidence_assessment_id,
                            *[agent_run.agent_run_id for agent_run in agent_runs],
                        ],
                        pipeline_event_ids=[
                            start_event.pipeline_event.pipeline_event_id,
                            completed_event.pipeline_event.pipeline_event_id,
                            attention_event.pipeline_event.pipeline_event_id,
                        ],
                        attention_reasons=["insufficient_evidence"],
                        notes=notes,
                        outputs_expected=True,
                    ),
                    output_root=monitoring_root,
                )
                return RunResearchWorkflowResponse(
                    research_workflow_id=research_workflow_id,
                    status="insufficient_evidence",
                    company_id=inputs.company_id,
                    hypothesis=None,
                    evidence_assessment=evidence_assessment,
                    counter_hypothesis=None,
                    research_brief=None,
                    memo=None,
                    retrieval_context=retrieval_context,
                    agent_runs=agent_runs,
                    storage_locations=storage_locations,
                    notes=notes,
                )

            hypothesis = hypothesis.model_copy(
                update={
                    "evidence_assessment_id": evidence_assessment.evidence_assessment_id,
                    "updated_at": self.clock.now(),
                }
            )

            critique_agent_run_id = make_prefixed_id("arun")
            counter_hypothesis = generate_counter_hypothesis(
                hypothesis=hypothesis,
                evidence_assessment=evidence_assessment,
                inputs=inputs,
                clock=self.clock,
                workflow_run_id=research_workflow_id,
                agent_run_id=critique_agent_run_id,
            )
            agent_runs.append(
                self._build_agent_run(
                    agent_name="counterargument_agent",
                    objective="Generate a disciplined counter-hypothesis that challenges assumptions and causal claims.",
                    input_artifact_ids=input_artifact_ids + [hypothesis.hypothesis_id],
                    output_artifact_ids=[counter_hypothesis.counter_hypothesis_id],
                    status=AgentRunStatus.SUCCEEDED,
                    workflow_run_id=research_workflow_id,
                    agent_run_id=critique_agent_run_id,
                    escalation_reason=None,
                )
            )

            brief_agent_run_id = make_prefixed_id("arun")
            research_brief = build_research_brief(
                hypothesis=hypothesis,
                counter_hypothesis=counter_hypothesis,
                evidence_assessment=evidence_assessment,
                inputs=inputs,
                clock=self.clock,
                workflow_run_id=research_workflow_id,
                agent_run_id=brief_agent_run_id,
            )
            agent_runs.append(
                self._build_agent_run(
                    agent_name="memo_writer_agent",
                    objective="Assemble a structured research brief and optional memo skeleton for human review.",
                    input_artifact_ids=[
                        hypothesis.hypothesis_id,
                        evidence_assessment.evidence_assessment_id,
                        counter_hypothesis.counter_hypothesis_id,
                    ],
                    output_artifact_ids=[research_brief.research_brief_id],
                    status=AgentRunStatus.SUCCEEDED,
                    workflow_run_id=research_workflow_id,
                    agent_run_id=brief_agent_run_id,
                    escalation_reason=None,
                )
            )

            memo = None
            if request.generate_memo_skeleton:
                memo = MemoGenerationService(clock=self.clock).generate(
                    MemoGenerationRequest(
                        research_brief=research_brief,
                        audience="research_review",
                        requested_by=request.requested_by,
                        author_agent_run_id=brief_agent_run_id,
                        retrieval_context=retrieval_context,
                    )
                ).memo

            storage_locations = self._persist_completed_workflow(
                output_root=resolved_output_root,
                inputs=inputs,
                hypothesis=hypothesis,
                evidence_assessment=evidence_assessment,
                counter_hypothesis=counter_hypothesis,
                research_brief=research_brief,
                memo=memo,
                agent_runs=agent_runs,
            )
            audit_response = AuditLoggingService(clock=self.clock).record_event(
                AuditEventRequest(
                    event_type="research_workflow_completed",
                    actor_type="service",
                    actor_id="research_orchestrator",
                    target_type="research_workflow",
                    target_id=research_workflow_id,
                    action="completed",
                    outcome=AuditOutcome.SUCCESS,
                    reason="Deterministic research workflow completed.",
                    request_id=research_workflow_id,
                    related_artifact_ids=[
                        hypothesis.hypothesis_id,
                        evidence_assessment.evidence_assessment_id,
                        counter_hypothesis.counter_hypothesis_id,
                        research_brief.research_brief_id,
                        *([memo.memo_id] if memo is not None else []),
                        *[agent_run.agent_run_id for agent_run in agent_runs],
                    ],
                    notes=notes,
                ),
                output_root=audit_root,
            )
            storage_locations.append(audit_response.storage_location)
            completed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="research_workflow",
                    workflow_run_id=research_workflow_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_COMPLETED,
                    status=WorkflowStatus.SUCCEEDED,
                    message="Research workflow completed successfully.",
                    related_artifact_ids=[
                        hypothesis.hypothesis_id,
                        evidence_assessment.evidence_assessment_id,
                        counter_hypothesis.counter_hypothesis_id,
                        research_brief.research_brief_id,
                        *([memo.memo_id] if memo is not None else []),
                    ],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="research_workflow",
                    workflow_run_id=research_workflow_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.SUCCEEDED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=storage_locations,
                    produced_artifact_ids=[
                        hypothesis.hypothesis_id,
                        evidence_assessment.evidence_assessment_id,
                        counter_hypothesis.counter_hypothesis_id,
                        research_brief.research_brief_id,
                        *([memo.memo_id] if memo is not None else []),
                        *[agent_run.agent_run_id for agent_run in agent_runs],
                    ],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        completed_event.pipeline_event.pipeline_event_id,
                    ],
                    notes=notes,
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            return RunResearchWorkflowResponse(
                research_workflow_id=research_workflow_id,
                status="completed",
                company_id=inputs.company_id,
                hypothesis=hypothesis,
                evidence_assessment=evidence_assessment,
                counter_hypothesis=counter_hypothesis,
                research_brief=research_brief,
                memo=memo,
                retrieval_context=retrieval_context,
                agent_runs=agent_runs,
                storage_locations=storage_locations,
                notes=notes,
            )
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="research_workflow",
                    workflow_run_id=research_workflow_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=f"Research workflow failed: {exc}",
                    related_artifact_ids=[],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="research_workflow",
                    workflow_run_id=research_workflow_id,
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
                    notes=[f"requested_by={request.requested_by}"],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise

    def _build_retrieval_context(
        self,
        *,
        request: RunResearchWorkflowRequest,
        resolved_output_root: Path,
        company_id: str,
        started_at: datetime,
    ) -> RetrievalContext:
        """Build advisory same-company retrieval context for a research workflow run."""

        query = RetrievalQuery(
            retrieval_query_id=make_prefixed_id("rqry"),
            scopes=[
                MemoryScope.EVIDENCE,
                MemoryScope.EVIDENCE_ASSESSMENT,
                MemoryScope.HYPOTHESIS,
                MemoryScope.COUNTER_HYPOTHESIS,
                MemoryScope.RESEARCH_BRIEF,
                MemoryScope.MEMO,
                MemoryScope.EXPERIMENT,
            ],
            company_id=company_id,
            time_end=started_at - timedelta(microseconds=1),
            limit=25,
        )
        response = ResearchMemoryService(clock=self.clock).search_research_memory(
            SearchResearchMemoryRequest(
                workspace_root=resolved_output_root.parent,
                research_root=resolved_output_root,
                parsing_root=request.parsing_root,
                ingestion_root=request.ingestion_root,
                query=query,
            )
        )
        return response.retrieval_context

    def _persist_partial_workflow(
        self,
        *,
        output_root: Path,
        inputs: LoadedResearchArtifacts,
        evidence_assessment: EvidenceAssessment,
        agent_runs: list[AgentRun],
    ) -> list[ArtifactStorageLocation]:
        """Persist assessment and agent runs when support is insufficient."""

        store = LocalResearchArtifactStore(
            root=output_root,
            clock=self.clock,
        )
        storage_locations = [
            store.persist_model(
                artifact_id=evidence_assessment.evidence_assessment_id,
                category="evidence_assessments",
                model=evidence_assessment,
                source_reference_ids=evidence_assessment.provenance.source_reference_ids,
            )
        ]
        storage_locations.extend(self._persist_agent_runs(store=store, agent_runs=agent_runs))
        return storage_locations

    def _persist_completed_workflow(
        self,
        *,
        output_root: Path,
        inputs: LoadedResearchArtifacts,
        hypothesis: Hypothesis,
        evidence_assessment: EvidenceAssessment,
        counter_hypothesis: CounterHypothesis,
        research_brief: ResearchBrief,
        memo: Memo | None,
        agent_runs: list[AgentRun],
    ) -> list[ArtifactStorageLocation]:
        """Persist all completed research workflow artifacts."""

        store = LocalResearchArtifactStore(
            root=output_root,
            clock=self.clock,
        )
        storage_locations = [
            store.persist_model(
                artifact_id=hypothesis.hypothesis_id,
                category="hypotheses",
                model=hypothesis,
                source_reference_ids=hypothesis.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=evidence_assessment.evidence_assessment_id,
                category="evidence_assessments",
                model=evidence_assessment,
                source_reference_ids=evidence_assessment.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=counter_hypothesis.counter_hypothesis_id,
                category="counter_hypotheses",
                model=counter_hypothesis,
                source_reference_ids=counter_hypothesis.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=research_brief.research_brief_id,
                category="research_briefs",
                model=research_brief,
                source_reference_ids=research_brief.provenance.source_reference_ids,
            ),
        ]
        if memo is not None:
            storage_locations.append(
                store.persist_model(
                    artifact_id=memo.memo_id,
                    category="memos",
                    model=memo,
                    source_reference_ids=memo.provenance.source_reference_ids,
                )
            )
        storage_locations.extend(self._persist_agent_runs(store=store, agent_runs=agent_runs))
        return storage_locations

    def _persist_agent_runs(
        self, *, store: LocalResearchArtifactStore, agent_runs: list[AgentRun]
    ) -> list[ArtifactStorageLocation]:
        """Persist agent-run records emitted by the research workflow."""

        return [
            store.persist_model(
                artifact_id=agent_run.agent_run_id,
                category="agent_runs",
                model=agent_run,
                source_reference_ids=agent_run.provenance.source_reference_ids,
            )
            for agent_run in agent_runs
        ]

    def _build_agent_run(
        self,
        *,
        agent_name: str,
        objective: str,
        input_artifact_ids: list[str],
        output_artifact_ids: list[str],
        status: AgentRunStatus,
        workflow_run_id: str,
        agent_run_id: str,
        escalation_reason: str | None,
    ) -> AgentRun:
        """Build one deterministic agent-run record."""

        now = self.clock.now()
        return AgentRun(
            agent_run_id=agent_run_id,
            agent_name=agent_name,
            agent_version=get_settings().app_version,
            objective=objective,
            model_name=None,
            prompt_version=None,
            input_artifact_ids=input_artifact_ids,
            output_artifact_ids=output_artifact_ids,
            status=status,
            started_at=now,
            completed_at=now,
            human_review_required=True,
            escalation_reason=escalation_reason,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="research_agent_run_record",
                upstream_artifact_ids=input_artifact_ids + output_artifact_ids,
                workflow_run_id=workflow_run_id,
                agent_run_id=agent_run_id,
                notes=[objective],
            ),
            created_at=now,
            updated_at=now,
        )


def _input_artifact_ids(inputs: LoadedResearchArtifacts) -> list[str]:
    """Return stable upstream artifact IDs for one research workflow run."""

    return sorted(
        {
            *[claim.extracted_claim_id for claim in inputs.claims],
            *[risk_factor.risk_factor_id for risk_factor in inputs.risk_factors],
            *[change.guidance_change_id for change in inputs.guidance_changes],
            *[marker.tone_marker_id for marker in inputs.tone_markers],
            *[span.evidence_span_id for span in inputs.evidence_spans],
        }
    )
