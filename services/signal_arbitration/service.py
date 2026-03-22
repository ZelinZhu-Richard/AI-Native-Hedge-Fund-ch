from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import resolve_artifact_workspace_from_stage_root
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArbitrationDecision,
    ArtifactStorageLocation,
    AuditOutcome,
    PipelineEventType,
    SignalBundle,
    SignalCalibration,
    SignalConflict,
    StrictModel,
    WorkflowStatus,
)
from libraries.utils import make_prefixed_id
from services.audit import AuditEventRequest, AuditLoggingService
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.signal_arbitration.loaders import load_signal_arbitration_inputs
from services.signal_arbitration.rules import (
    build_arbitration_decision,
    build_signal_calibrations,
    detect_signal_conflicts,
)
from services.signal_arbitration.storage import LocalSignalArbitrationArtifactStore


class RunSignalArbitrationRequest(StrictModel):
    """Explicit local request to compare and arbitrate persisted same-company signals."""

    signal_root: Path = Field(description="Root path containing persisted signal artifacts.")
    research_root: Path = Field(description="Root path containing persisted research artifacts.")
    output_root: Path | None = Field(
        default=None,
        description="Optional signal-arbitration artifact root.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when the signal root contains multiple companies.",
    )
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional point-in-time cutoff for arbitration inputs.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunSignalArbitrationResponse(StrictModel):
    """Result of the deterministic Day 19 signal-arbitration workflow."""

    company_id: str | None = Field(
        default=None,
        description="Covered company identifier when arbitration resolved one company slice.",
    )
    signal_bundle: SignalBundle | None = Field(
        default=None,
        description="Persisted signal bundle when at least one source signal was available.",
    )
    signal_calibrations: list[SignalCalibration] = Field(
        default_factory=list,
        description="Calibration rows derived from the visible signals.",
    )
    signal_conflicts: list[SignalConflict] = Field(
        default_factory=list,
        description="Conflicts observed during deterministic arbitration.",
    )
    arbitration_decision: ArbitrationDecision | None = Field(
        default=None,
        description="Persisted arbitration decision when arbitration ran.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing exclusions, conflicts, or no-op paths.",
    )


class SignalArbitrationService(BaseService):
    """Calibrate, compare, and arbitrate multiple same-company signal artifacts."""

    capability_name = "signal_arbitration"
    capability_description = (
        "Builds deterministic signal calibrations, detects conflicts, and persists review-facing signal bundles."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Signal", "EvidenceAssessment"],
            produces=["SignalCalibration", "SignalConflict", "ArbitrationDecision", "SignalBundle"],
            api_routes=[],
        )

    def run_signal_arbitration(
        self,
        request: RunSignalArbitrationRequest,
    ) -> RunSignalArbitrationResponse:
        """Execute the deterministic Day 19 arbitration workflow."""

        workflow_run_id = make_prefixed_id("sarbit")
        output_root = request.output_root or (
            get_settings().resolved_artifact_root / "signal_arbitration"
        )
        workspace = resolve_artifact_workspace_from_stage_root(output_root)
        audit_root = workspace.audit_root
        monitoring_root = workspace.monitoring_root
        started_at = self.clock.now()
        monitoring_service = MonitoringService(clock=self.clock)
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="signal_arbitration",
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message="Signal arbitration workflow started.",
                related_artifact_ids=[],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )

        try:
            inputs = load_signal_arbitration_inputs(
                signal_root=request.signal_root,
                research_root=request.research_root,
                company_id=request.company_id,
                as_of_time=request.as_of_time,
            )
            notes: list[str] = []
            if request.as_of_time is None:
                notes.append(
                    "No as_of_time provided; latest-artifact arbitration is a local-development convenience and not replay-safe."
                )
            else:
                notes.append(f"as_of_time={request.as_of_time.isoformat()}")
            if not inputs.signals:
                notes.append("No signals were available for arbitration.")
                completed_event = monitoring_service.record_pipeline_event(
                    RecordPipelineEventRequest(
                        workflow_name="signal_arbitration",
                        workflow_run_id=workflow_run_id,
                        service_name=self.capability_name,
                        event_type=PipelineEventType.RUN_COMPLETED,
                        status=WorkflowStatus.PARTIAL,
                        message="Signal arbitration completed without any source signals.",
                        related_artifact_ids=[],
                        notes=notes,
                    ),
                    output_root=monitoring_root,
                )
                run_summary_response = monitoring_service.record_run_summary(
                    RecordRunSummaryRequest(
                        workflow_name="signal_arbitration",
                        workflow_run_id=workflow_run_id,
                        service_name=self.capability_name,
                        requested_by=request.requested_by,
                        status=WorkflowStatus.PARTIAL,
                        started_at=started_at,
                        completed_at=self.clock.now(),
                        storage_locations=[],
                        produced_artifact_ids=[],
                        pipeline_event_ids=[
                            start_event.pipeline_event.pipeline_event_id,
                            completed_event.pipeline_event.pipeline_event_id,
                        ],
                        failure_messages=[],
                        attention_reasons=["No signals were available for arbitration."],
                        notes=notes,
                        outputs_expected=False,
                    ),
                    output_root=monitoring_root,
                )
                return RunSignalArbitrationResponse(
                    company_id=inputs.company_id,
                    storage_locations=run_summary_response.storage_locations,
                    notes=notes,
                )

            candidates, excluded_signals = build_signal_calibrations(
                signals=inputs.signals,
                evidence_assessments_by_hypothesis_id=inputs.evidence_assessments_by_hypothesis_id,
                as_of_time=request.as_of_time,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
            conflicts = detect_signal_conflicts(
                candidates=candidates,
                as_of_time=request.as_of_time,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
            decision, bundle = build_arbitration_decision(
                company_id=inputs.company_id,
                component_signals=inputs.signals,
                candidates=candidates,
                excluded_signals=excluded_signals,
                conflicts=conflicts,
                as_of_time=request.as_of_time,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
            store = LocalSignalArbitrationArtifactStore(root=output_root, clock=self.clock)
            storage_locations: list[ArtifactStorageLocation] = []
            for candidate in candidates:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=candidate.calibration.signal_calibration_id,
                        category="signal_calibrations",
                        model=candidate.calibration,
                        source_reference_ids=candidate.signal.provenance.source_reference_ids,
                    )
                )
            for conflict in conflicts:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=conflict.signal_conflict_id,
                        category="signal_conflicts",
                        model=conflict,
                        source_reference_ids=conflict.provenance.source_reference_ids,
                    )
                )
            storage_locations.append(
                store.persist_model(
                    artifact_id=decision.arbitration_decision_id,
                    category="arbitration_decisions",
                    model=decision,
                    source_reference_ids=decision.provenance.source_reference_ids,
                )
            )
            if bundle is not None:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=bundle.signal_bundle_id,
                        category="signal_bundles",
                        model=bundle,
                        source_reference_ids=bundle.provenance.source_reference_ids,
                    )
                )
            status = (
                WorkflowStatus.ATTENTION_REQUIRED
                if decision.selected_primary_signal_id is None or bool(conflicts) or not candidates
                else WorkflowStatus.SUCCEEDED
            )
            if decision.selected_primary_signal_id is None:
                notes.append("Arbitration intentionally withheld a primary signal selection.")
            if not candidates:
                notes.append("All visible signals were excluded before deterministic calibration.")
            if excluded_signals:
                notes.append(f"excluded_signal_count={len(excluded_signals)}")
                reason_counts: dict[str, int] = {}
                for excluded in excluded_signals:
                    reason_counts[excluded.reason.value] = (
                        reason_counts.get(excluded.reason.value, 0) + 1
                    )
                notes.extend(
                    f"excluded_signal_reason_count[{reason}]={count}"
                    for reason, count in sorted(reason_counts.items())
                )
            if conflicts:
                notes.append(f"signal_conflict_count={len(conflicts)}")
            completed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="signal_arbitration",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    event_type=(
                        PipelineEventType.ATTENTION_REQUIRED
                        if status is WorkflowStatus.ATTENTION_REQUIRED
                        else PipelineEventType.RUN_COMPLETED
                    ),
                    status=status,
                    message=decision.summary,
                    related_artifact_ids=[
                        *([bundle.signal_bundle_id] if bundle is not None else []),
                        decision.arbitration_decision_id,
                        *[conflict.signal_conflict_id for conflict in conflicts],
                    ],
                    notes=notes,
                ),
                output_root=monitoring_root,
            )
            audit_response = AuditLoggingService(clock=self.clock).record_event(
                AuditEventRequest(
                    event_type="signal_arbitration_completed",
                    actor_type="service",
                    actor_id=self.capability_name,
                    target_type="signal_bundle" if bundle is not None else "arbitration_decision",
                    target_id=(
                        bundle.signal_bundle_id
                        if bundle is not None
                        else decision.arbitration_decision_id
                    ),
                    action="completed",
                    outcome=(
                        AuditOutcome.WARNING
                        if status is WorkflowStatus.ATTENTION_REQUIRED
                        else AuditOutcome.SUCCESS
                    ),
                    reason=decision.summary,
                    request_id=workflow_run_id,
                    related_artifact_ids=[
                        *([bundle.signal_bundle_id] if bundle is not None else []),
                        decision.arbitration_decision_id,
                        *[candidate.calibration.signal_calibration_id for candidate in candidates],
                        *[conflict.signal_conflict_id for conflict in conflicts],
                    ],
                    notes=notes,
                ),
                output_root=audit_root,
            )
            storage_locations.append(audit_response.storage_location)
            run_summary_response = monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="signal_arbitration",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=status,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=storage_locations,
                    produced_artifact_ids=[
                        *([bundle.signal_bundle_id] if bundle is not None else []),
                        decision.arbitration_decision_id,
                        *[candidate.calibration.signal_calibration_id for candidate in candidates],
                        *[conflict.signal_conflict_id for conflict in conflicts],
                    ],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        completed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[],
                    attention_reasons=(
                        [decision.summary] if status is WorkflowStatus.ATTENTION_REQUIRED else []
                    ),
                    notes=notes,
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            storage_locations.extend(run_summary_response.storage_locations)
            return RunSignalArbitrationResponse(
                company_id=inputs.company_id,
                signal_bundle=bundle,
                signal_calibrations=[candidate.calibration for candidate in candidates],
                signal_conflicts=conflicts,
                arbitration_decision=decision,
                storage_locations=storage_locations,
                notes=notes,
            )
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="signal_arbitration",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message="Signal arbitration workflow failed.",
                    related_artifact_ids=[],
                    notes=[str(exc)],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="signal_arbitration",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=[],
                    produced_artifact_ids=[],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    attention_reasons=[],
                    notes=[],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise
