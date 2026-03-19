from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from libraries.schemas.base import (
    AuditOutcome,
    ProvenanceRecord,
    Severity,
    StrictModel,
    TimestampedModel,
)
from libraries.schemas.storage import ArtifactStorageLocation


class WorkflowStatus(StrEnum):
    """Operational status for a monitored workflow run."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    ATTENTION_REQUIRED = "attention_required"


class HealthCheckStatus(StrEnum):
    """Outcome status for one health or readiness check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class PipelineEventType(StrEnum):
    """Coarse-grained operational events for monitored workflows."""

    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    ATTENTION_REQUIRED = "attention_required"
    ARTIFACT_WRITTEN = "artifact_written"
    REVIEW_ACTION = "review_action"


class AlertState(StrEnum):
    """Lifecycle for a monitoring alert record."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AuditLog(TimestampedModel):
    """Immutable record of a material action taken by a human or system."""

    audit_log_id: str = Field(description="Canonical audit log identifier.")
    event_type: str = Field(description="Normalized event type.")
    actor_type: str = Field(description="Actor category, such as `human`, `service`, or `agent`.")
    actor_id: str = Field(description="Actor identifier.")
    target_type: str = Field(description="Entity type acted upon.")
    target_id: str = Field(description="Entity identifier acted upon.")
    action: str = Field(description="Action performed.")
    outcome: AuditOutcome = Field(description="Outcome of the action.")
    occurred_at: datetime = Field(description="UTC timestamp when the action occurred.")
    reason: str | None = Field(default=None, description="Optional reason for the action.")
    request_id: str | None = Field(default=None, description="Request or trace identifier.")
    status_before: str | None = Field(
        default=None,
        description="Optional lifecycle status before the action was applied.",
    )
    status_after: str | None = Field(
        default=None,
        description="Optional lifecycle status after the action was applied.",
    )
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts associated with the event.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the audit event.")


class PipelineEvent(TimestampedModel):
    """Persisted milestone event for one monitored workflow run."""

    pipeline_event_id: str = Field(description="Canonical pipeline event identifier.")
    workflow_name: str = Field(description="Workflow name for the monitored run.")
    workflow_run_id: str = Field(description="Workflow run identifier.")
    service_name: str = Field(description="Owning service name.")
    event_type: PipelineEventType = Field(description="Coarse-grained pipeline event type.")
    status: WorkflowStatus = Field(description="Workflow status at the time of the event.")
    occurred_at: datetime = Field(description="UTC timestamp when the event occurred.")
    message: str = Field(description="Human-readable event summary.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly associated with the event.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the pipeline event.")


class AlertCondition(TimestampedModel):
    """Static alert rule definition used by the local monitoring layer."""

    alert_condition_id: str = Field(description="Canonical alert-condition identifier.")
    name: str = Field(description="Stable alert condition name.")
    service_name: str = Field(description="Owning service or subsystem for the condition.")
    workflow_name: str | None = Field(
        default=None,
        description="Optional workflow scope for the condition.",
    )
    severity: Severity = Field(description="Default severity for records emitted by the condition.")
    description: str = Field(description="Human-readable condition description.")
    enabled: bool = Field(default=True, description="Whether the condition is active.")
    provenance: ProvenanceRecord = Field(description="Traceability for the alert condition.")


class AlertRecord(TimestampedModel):
    """Recorded alert emitted by the local monitoring layer."""

    alert_record_id: str = Field(description="Canonical alert-record identifier.")
    alert_condition_id: str = Field(description="Condition identifier that emitted the alert.")
    service_name: str = Field(description="Affected service name.")
    workflow_name: str | None = Field(
        default=None,
        description="Optional workflow name affected by the alert.",
    )
    workflow_run_id: str | None = Field(
        default=None,
        description="Optional workflow run identifier affected by the alert.",
    )
    severity: Severity = Field(description="Severity recorded for the alert.")
    state: AlertState = Field(description="Current alert lifecycle state.")
    triggered_at: datetime = Field(description="UTC timestamp when the alert was triggered.")
    message: str = Field(description="Human-readable alert summary.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly associated with the alert.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the alert record.")


class HealthCheck(TimestampedModel):
    """Persisted result of one health or readiness check."""

    health_check_id: str = Field(description="Canonical health-check identifier.")
    service_name: str = Field(description="Service or subsystem being checked.")
    check_name: str = Field(description="Stable health check name.")
    status: HealthCheckStatus = Field(description="Outcome of the health check.")
    checked_at: datetime = Field(description="UTC timestamp when the check was evaluated.")
    message: str = Field(description="Human-readable health summary.")
    details: dict[str, str] = Field(
        default_factory=dict,
        description="Structured detail fields for debugging or dashboards.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the health check.")


class RunSummary(TimestampedModel):
    """Primary monitoring artifact describing one workflow run outcome."""

    run_summary_id: str = Field(description="Canonical run-summary identifier.")
    workflow_name: str = Field(description="Workflow name for the monitored run.")
    workflow_run_id: str = Field(description="Workflow run identifier.")
    service_name: str = Field(description="Owning service name.")
    status: WorkflowStatus = Field(description="Terminal or current workflow status.")
    requested_by: str = Field(description="Requester or workflow owner.")
    started_at: datetime = Field(description="UTC timestamp when the run began.")
    completed_at: datetime = Field(description="UTC timestamp when the run completed or failed.")
    produced_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts materially produced by the run.",
    )
    produced_artifact_counts: dict[str, int] = Field(
        default_factory=dict,
        description="High-level artifact counts keyed by category.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Persisted artifact storage locations written by the run.",
    )
    pipeline_event_ids: list[str] = Field(
        default_factory=list,
        description="Pipeline events associated with the run.",
    )
    alert_record_ids: list[str] = Field(
        default_factory=list,
        description="Alerts associated with the run.",
    )
    failure_messages: list[str] = Field(
        default_factory=list,
        description="Failure messages captured for the run.",
    )
    attention_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons the run needs operator attention.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing outputs or caveats.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the run summary.")

    @model_validator(mode="after")
    def validate_run_summary(self) -> RunSummary:
        """Require ordered timestamps and non-negative artifact counts."""

        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at.")
        if any(count < 0 for count in self.produced_artifact_counts.values()):
            raise ValueError("produced_artifact_counts values must be non-negative.")
        return self


class ServiceStatus(StrictModel):
    """Derived health view for one registered service."""

    service_name: str = Field(description="Registered service name.")
    capability_description: str = Field(description="Service responsibility summary.")
    status: HealthCheckStatus = Field(description="Derived current service status.")
    last_checked_at: datetime = Field(description="Most recent health derivation timestamp.")
    recent_run_summary_ids: list[str] = Field(
        default_factory=list,
        description="Recent run summaries associated with the service.",
    )
    open_alert_count: int = Field(
        default=0,
        ge=0,
        description="Count of currently open alerts affecting the service.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operator-facing status notes.",
    )
