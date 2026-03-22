from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import resolve_artifact_workspace_from_stage_root
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AblationView,
    ArtifactStorageLocation,
    AuditOutcome,
    PipelineEventType,
    Signal,
    SignalScore,
    StrictModel,
    TimingAnomaly,
    WorkflowStatus,
)
from libraries.utils import make_prefixed_id
from services.audit import AuditEventRequest, AuditLoggingService
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.signal_generation.loaders import load_signal_generation_inputs
from services.signal_generation.scoring import build_candidate_signals
from services.signal_generation.storage import LocalSignalArtifactStore
from services.timing import TimingService


class SignalGenerationRequest(StrictModel):
    """Request to build signals from reviewed hypotheses and point-in-time features."""

    company_id: str = Field(description="Covered company identifier.")
    hypothesis_ids: list[str] = Field(
        default_factory=list, description="Input hypothesis identifiers."
    )
    feature_ids: list[str] = Field(default_factory=list, description="Input feature identifiers.")
    as_of_time: datetime = Field(
        description="Maximum information time allowed for signal generation."
    )
    requested_by: str = Field(description="Requester identifier.")


class SignalGenerationResponse(StrictModel):
    """Response returned after accepting a signal generation request."""

    signal_batch_id: str = Field(description="Identifier for the signal generation batch.")
    signal_ids: list[str] = Field(default_factory=list, description="Reserved signal identifiers.")
    status: str = Field(description="Operational status.")
    review_required: bool = Field(description="Whether resulting signals require human review.")
    accepted_at: datetime = Field(description="UTC timestamp when the batch was accepted.")


class RunSignalGenerationWorkflowRequest(StrictModel):
    """Explicit local request to build candidate signals from Day 5 feature artifacts."""

    feature_root: Path = Field(description="Root path for persisted feature artifacts.")
    research_root: Path | None = Field(
        default=None,
        description="Optional research artifact root used to reload thesis and evidence context.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional signal artifact root. Defaults to the configured artifact root.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when the feature root contains multiple companies.",
    )
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional feature cutoff. When omitted, latest-artifact loading is used for local development only.",
    )
    ablation_view: AblationView = Field(
        default=AblationView.TEXT_ONLY,
        description="Requested ablation slice for signal generation.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunSignalGenerationWorkflowResponse(StrictModel):
    """Result of a local Day 5 signal-generation workflow."""

    signal_generation_run_id: str = Field(description="Canonical workflow identifier.")
    company_id: str = Field(description="Covered company identifier.")
    signals: list[Signal] = Field(
        default_factory=list,
        description="Candidate signals emitted by the workflow.",
    )
    signal_scores: list[SignalScore] = Field(
        default_factory=list,
        description="Signal-score components emitted by the workflow.",
    )
    timing_anomalies: list[TimingAnomaly] = Field(
        default_factory=list,
        description="Structured timing anomalies observed during signal availability resolution.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work, assumptions, or gaps.",
    )


class SignalGenerationService(BaseService):
    """Generate Day 5 candidate signals from candidate features."""

    capability_name = "signal_generation"
    capability_description = "Builds candidate signals from candidate features and research lineage."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Feature", "ResearchBrief", "EvidenceAssessment"],
            produces=["Signal", "SignalScore"],
            api_routes=[],
        )

    def generate_signals(self, request: SignalGenerationRequest) -> SignalGenerationResponse:
        """Reserve identifiers for a future signal generation batch."""

        return SignalGenerationResponse(
            signal_batch_id=make_prefixed_id("signalbatch"),
            signal_ids=[make_prefixed_id("sig")],
            status="queued",
            review_required=True,
            accepted_at=self.clock.now(),
        )

    def run_signal_generation_workflow(
        self,
        request: RunSignalGenerationWorkflowRequest,
    ) -> RunSignalGenerationWorkflowResponse:
        """Execute deterministic Day 5 signal generation from persisted feature artifacts."""

        signal_generation_run_id = make_prefixed_id("sgen")
        output_root = request.output_root or (
            get_settings().resolved_artifact_root / "signal_generation"
        )
        output_workspace = resolve_artifact_workspace_from_stage_root(output_root)
        feature_workspace = resolve_artifact_workspace_from_stage_root(request.feature_root)
        audit_root = output_workspace.audit_root
        monitoring_root = output_workspace.monitoring_root
        timing_root = output_workspace.timing_root
        monitoring_service = MonitoringService(clock=self.clock)
        started_at = self.clock.now()
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="signal_generation",
                workflow_run_id=signal_generation_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message="Signal generation workflow started.",
                related_artifact_ids=[],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        inferred_research_root = request.research_root
        if inferred_research_root is None:
            sibling_research_root = feature_workspace.research_root
            inferred_research_root = sibling_research_root if sibling_research_root.exists() else None

        try:
            inputs = load_signal_generation_inputs(
                feature_root=request.feature_root,
                research_root=inferred_research_root,
                company_id=request.company_id,
                as_of_time=request.as_of_time,
            )
            result = build_candidate_signals(
                inputs=inputs,
                ablation_view=request.ablation_view,
                clock=self.clock,
                workflow_run_id=signal_generation_run_id,
            )
            store = LocalSignalArtifactStore(root=output_root, clock=self.clock)
            storage_locations: list[ArtifactStorageLocation] = []
            for signal_score in result.signal_scores:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=signal_score.signal_score_id,
                        category="signal_scores",
                        model=signal_score,
                        source_reference_ids=[],
                    )
                )
            for signal in result.signals:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=signal.signal_id,
                        category="signals",
                        model=signal,
                        source_reference_ids=signal.provenance.source_reference_ids,
                    )
                )
            if result.timing_anomalies:
                timing_response = TimingService(clock=self.clock).persist_anomalies(
                    anomalies=result.timing_anomalies,
                    output_root=timing_root,
                )
                storage_locations.extend(timing_response.storage_locations)
            notes = list(result.notes)
            if request.as_of_time is None:
                notes.append(
                    "No as_of_time provided; latest-artifact loading is a local-development convenience and not replay-safe."
                )
            else:
                notes.append(f"as_of_time={request.as_of_time.isoformat()}")
            audit_response = AuditLoggingService(clock=self.clock).record_event(
                AuditEventRequest(
                    event_type=(
                        "signal_generation_completed"
                        if result.signals
                        else "signal_generation_blocked"
                    ),
                    actor_type="service",
                    actor_id="signal_generation",
                    target_type="signal_generation_workflow",
                    target_id=signal_generation_run_id,
                    action="completed" if result.signals else "blocked",
                    outcome=AuditOutcome.SUCCESS if result.signals else AuditOutcome.WARNING,
                    reason=(
                        "Candidate signals were materialized from candidate features."
                        if result.signals
                        else "No candidate signals were emitted for the requested ablation view."
                    ),
                    request_id=signal_generation_run_id,
                    related_artifact_ids=[
                        *[signal_score.signal_score_id for signal_score in result.signal_scores],
                        *[signal.signal_id for signal in result.signals],
                        *[anomaly.timing_anomaly_id for anomaly in result.timing_anomalies],
                    ],
                    notes=notes,
                ),
                output_root=audit_root,
            )
            storage_locations.append(audit_response.storage_location)
            completed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="signal_generation",
                    workflow_run_id=signal_generation_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_COMPLETED,
                    status=WorkflowStatus.SUCCEEDED,
                    message=(
                        "Signal generation workflow completed."
                        if result.signals
                        else "Signal generation workflow completed without candidate signals."
                    ),
                    related_artifact_ids=[
                        *[signal_score.signal_score_id for signal_score in result.signal_scores],
                        *[signal.signal_id for signal in result.signals],
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
            if not result.signals:
                attention_event = monitoring_service.record_pipeline_event(
                    RecordPipelineEventRequest(
                        workflow_name="signal_generation",
                        workflow_run_id=signal_generation_run_id,
                        service_name=self.capability_name,
                        event_type=PipelineEventType.ATTENTION_REQUIRED,
                        status=WorkflowStatus.ATTENTION_REQUIRED,
                        message="Signal generation emitted no candidate signals.",
                        related_artifact_ids=[],
                        notes=[f"requested_by={request.requested_by}"],
                    ),
                    output_root=monitoring_root,
                )
                pipeline_event_ids.append(attention_event.pipeline_event.pipeline_event_id)
                summary_status = WorkflowStatus.ATTENTION_REQUIRED
                attention_reasons.append("no_candidate_signals")
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="signal_generation",
                    workflow_run_id=signal_generation_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=summary_status,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=storage_locations,
                    produced_artifact_ids=[
                        *[signal_score.signal_score_id for signal_score in result.signal_scores],
                        *[signal.signal_id for signal in result.signals],
                        *[anomaly.timing_anomaly_id for anomaly in result.timing_anomalies],
                    ],
                    pipeline_event_ids=pipeline_event_ids,
                    attention_reasons=attention_reasons,
                    notes=notes,
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            return RunSignalGenerationWorkflowResponse(
                signal_generation_run_id=signal_generation_run_id,
                company_id=inputs.company_id,
                signals=result.signals,
                signal_scores=result.signal_scores,
                timing_anomalies=result.timing_anomalies,
                storage_locations=storage_locations,
                notes=notes,
            )
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="signal_generation",
                    workflow_run_id=signal_generation_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=f"Signal generation workflow failed: {exc}",
                    related_artifact_ids=[],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="signal_generation",
                    workflow_run_id=signal_generation_run_id,
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
