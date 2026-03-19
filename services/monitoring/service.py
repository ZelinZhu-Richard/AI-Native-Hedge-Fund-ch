from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.config import get_settings
from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AlertCondition,
    AlertRecord,
    AlertState,
    ArtifactStorageLocation,
    EvaluationReport,
    FailureCase,
    HealthCheck,
    HealthCheckStatus,
    PipelineEvent,
    PipelineEventType,
    RobustnessCheck,
    RunSummary,
    ServiceStatus,
    Severity,
    StrictModel,
    WorkflowStatus,
)
from libraries.utils import make_canonical_id
from services.monitoring.storage import LocalMonitoringArtifactStore, load_models
from services.monitoring.summaries import (
    artifact_ids_from_storage_locations,
    attention_reasons_from_ablation,
    dedupe_preserve_order,
    derive_ablation_run_status,
    derive_service_status,
    merged_artifact_counts,
)

TModel = TypeVar("TModel", bound=StrictModel)


class RecordPipelineEventRequest(StrictModel):
    """Request to persist one coarse-grained pipeline event."""

    workflow_name: str = Field(description="Workflow name for the monitored run.")
    workflow_run_id: str = Field(description="Workflow run identifier.")
    service_name: str = Field(description="Owning service name.")
    event_type: PipelineEventType = Field(description="Coarse-grained pipeline event type.")
    status: WorkflowStatus = Field(description="Workflow status at the time of the event.")
    message: str = Field(description="Human-readable event summary.")
    related_artifact_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RecordPipelineEventResponse(StrictModel):
    """Response returned after recording one pipeline event."""

    pipeline_event: PipelineEvent = Field(description="Persisted pipeline event.")
    storage_location: ArtifactStorageLocation = Field(
        description="Storage metadata for the pipeline event."
    )


class RecordRunSummaryRequest(StrictModel):
    """Request to persist one monitoring run summary."""

    workflow_name: str = Field(description="Workflow name for the monitored run.")
    workflow_run_id: str = Field(description="Workflow run identifier.")
    service_name: str = Field(description="Owning service name.")
    requested_by: str = Field(description="Requester or workflow owner.")
    status: WorkflowStatus = Field(description="Terminal or current workflow status.")
    started_at: datetime = Field(description="UTC timestamp when the run began.")
    completed_at: datetime = Field(description="UTC timestamp when the run completed or failed.")
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    produced_artifact_ids: list[str] = Field(default_factory=list)
    produced_artifact_counts: dict[str, int] = Field(default_factory=dict)
    pipeline_event_ids: list[str] = Field(default_factory=list)
    failure_messages: list[str] = Field(default_factory=list)
    attention_reasons: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    outputs_expected: bool = Field(
        default=False,
        description="Whether the workflow was expected to materialize outputs.",
    )


class RecordRunSummaryResponse(StrictModel):
    """Response returned after persisting one run summary."""

    run_summary: RunSummary = Field(description="Persisted run summary.")
    alert_records: list[AlertRecord] = Field(default_factory=list)
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)


class RunHealthChecksRequest(StrictModel):
    """Request to evaluate current local health and readiness."""

    artifact_root: Path | None = Field(default=None)
    monitoring_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    limit_recent_runs: int = Field(default=5, ge=1, le=50)


class RunHealthChecksResponse(StrictModel):
    """Persisted health-check and service-status results."""

    health_checks: list[HealthCheck] = Field(default_factory=list)
    alert_records: list[AlertRecord] = Field(default_factory=list)
    service_statuses: list[ServiceStatus] = Field(default_factory=list)
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ListRecentRunSummariesRequest(StrictModel):
    """Request to list recent persisted run summaries."""

    monitoring_root: Path | None = Field(default=None)
    service_name: str | None = Field(default=None)
    workflow_name: str | None = Field(default=None)
    limit: int = Field(default=20, ge=1, le=100)


class ListRecentRunSummariesResponse(StrictModel):
    """Recent monitoring run summaries."""

    items: list[RunSummary] = Field(default_factory=list)
    total: int = Field(description="Count of returned run summaries.")
    notes: list[str] = Field(default_factory=list)


class ListRecentFailureSummariesRequest(StrictModel):
    """Request to list recent failed or attention-required summaries."""

    monitoring_root: Path | None = Field(default=None)
    service_name: str | None = Field(default=None)
    limit: int = Field(default=20, ge=1, le=100)


class ListRecentFailureSummariesResponse(StrictModel):
    """Recent failed or attention-required run summaries plus open alerts."""

    run_summaries: list[RunSummary] = Field(default_factory=list)
    alert_records: list[AlertRecord] = Field(default_factory=list)
    total_runs: int = Field(description="Count of returned failure summaries.")
    total_alerts: int = Field(description="Count of returned open alerts.")
    notes: list[str] = Field(default_factory=list)


class GetServiceStatusesRequest(StrictModel):
    """Request to derive current service statuses from monitoring artifacts."""

    monitoring_root: Path | None = Field(default=None)
    limit_recent_runs: int = Field(default=5, ge=1, le=50)


class GetServiceStatusesResponse(StrictModel):
    """Derived current statuses for registered services."""

    items: list[ServiceStatus] = Field(default_factory=list)
    total: int = Field(description="Count of returned service statuses.")
    notes: list[str] = Field(default_factory=list)


class MonitoringService(BaseService):
    """Persist concise run summaries, alerts, and local health data."""

    capability_name = "monitoring"
    capability_description = (
        "Summarizes workflow runs, records alerts, and exposes local health and readiness."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["workflow responses", "health probes", "artifact metadata"],
            produces=[
                "RunSummary",
                "PipelineEvent",
                "HealthCheck",
                "AlertRecord",
                "ServiceStatus",
            ],
            api_routes=[
                "GET /health/details",
                "GET /monitoring/run-summaries/recent",
                "GET /monitoring/failures/recent",
                "GET /monitoring/services",
            ],
        )

    def record_pipeline_event(
        self,
        request: RecordPipelineEventRequest,
        *,
        output_root: Path | None = None,
    ) -> RecordPipelineEventResponse:
        """Persist one coarse-grained pipeline event."""

        monitoring_root = self._resolve_monitoring_root(output_root)
        store = LocalMonitoringArtifactStore(root=monitoring_root, clock=self.clock)
        now = self.clock.now()
        pipeline_event = PipelineEvent(
            pipeline_event_id=make_canonical_id(
                "pevt",
                request.service_name,
                request.workflow_name,
                request.workflow_run_id,
                request.event_type.value,
                request.message,
            ),
            workflow_name=request.workflow_name,
            workflow_run_id=request.workflow_run_id,
            service_name=request.service_name,
            event_type=request.event_type,
            status=request.status,
            occurred_at=now,
            message=request.message,
            related_artifact_ids=dedupe_preserve_order(request.related_artifact_ids),
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="monitoring_pipeline_event",
                upstream_artifact_ids=dedupe_preserve_order(request.related_artifact_ids),
                workflow_run_id=request.workflow_run_id,
                notes=request.notes,
            ),
            created_at=now,
            updated_at=now,
        )
        storage_location = store.persist_model(
            artifact_id=pipeline_event.pipeline_event_id,
            category="pipeline_events",
            model=pipeline_event,
            source_reference_ids=pipeline_event.provenance.source_reference_ids,
        )
        return RecordPipelineEventResponse(
            pipeline_event=pipeline_event,
            storage_location=storage_location,
        )

    def record_run_summary(
        self,
        request: RecordRunSummaryRequest,
        *,
        output_root: Path | None = None,
    ) -> RecordRunSummaryResponse:
        """Persist one primary monitoring artifact for a workflow run."""

        monitoring_root = self._resolve_monitoring_root(output_root)
        store = LocalMonitoringArtifactStore(root=monitoring_root, clock=self.clock)
        conditions, condition_storage_locations = self._ensure_default_alert_conditions(
            monitoring_root=monitoring_root,
            store=store,
        )
        existing_alerts = self._load_category(
            monitoring_root=monitoring_root,
            category="alert_records",
            model_cls=AlertRecord,
        )
        produced_artifact_ids = dedupe_preserve_order(
            [
                *request.produced_artifact_ids,
                *artifact_ids_from_storage_locations(request.storage_locations),
            ]
        )
        produced_artifact_counts = merged_artifact_counts(
            storage_locations=request.storage_locations,
            explicit_counts=request.produced_artifact_counts,
        )

        alert_records: list[AlertRecord] = []
        alert_storage_locations: list[ArtifactStorageLocation] = []
        if request.status is WorkflowStatus.FAILED:
            workflow_failed_alert, alert_storage = self._ensure_alert_record(
                monitoring_root=monitoring_root,
                store=store,
                existing_alerts=existing_alerts,
                condition=conditions["workflow_failed"],
                service_name=request.service_name,
                workflow_name=request.workflow_name,
                workflow_run_id=request.workflow_run_id,
                message=(
                    request.failure_messages[0]
                    if request.failure_messages
                    else "Workflow failed before producing a complete summary."
                ),
                related_artifact_ids=[
                    request.workflow_run_id,
                    *request.pipeline_event_ids,
                    *produced_artifact_ids,
                ],
            )
            alert_records.append(workflow_failed_alert)
            if alert_storage is not None:
                alert_storage_locations.append(alert_storage)
        if request.status is WorkflowStatus.ATTENTION_REQUIRED:
            attention_alert, alert_storage = self._ensure_alert_record(
                monitoring_root=monitoring_root,
                store=store,
                existing_alerts=existing_alerts,
                condition=conditions["attention_required"],
                service_name=request.service_name,
                workflow_name=request.workflow_name,
                workflow_run_id=request.workflow_run_id,
                message=(
                    request.attention_reasons[0]
                    if request.attention_reasons
                    else "Workflow completed but requires explicit operator attention."
                ),
                related_artifact_ids=[
                    request.workflow_run_id,
                    *request.pipeline_event_ids,
                    *produced_artifact_ids,
                ],
            )
            alert_records.append(attention_alert)
            if alert_storage is not None:
                alert_storage_locations.append(alert_storage)
        if request.outputs_expected and not produced_artifact_ids:
            output_alert, alert_storage = self._ensure_alert_record(
                monitoring_root=monitoring_root,
                store=store,
                existing_alerts=existing_alerts,
                condition=conditions["zero_outputs_when_outputs_expected"],
                service_name=request.service_name,
                workflow_name=request.workflow_name,
                workflow_run_id=request.workflow_run_id,
                message="Workflow reported completion but produced no persisted outputs.",
                related_artifact_ids=[request.workflow_run_id, *request.pipeline_event_ids],
            )
            alert_records.append(output_alert)
            if alert_storage is not None:
                alert_storage_locations.append(alert_storage)

        now = self.clock.now()
        run_summary = RunSummary(
            run_summary_id=make_canonical_id(
                "runsum",
                request.service_name,
                request.workflow_name,
                request.workflow_run_id,
            ),
            workflow_name=request.workflow_name,
            workflow_run_id=request.workflow_run_id,
            service_name=request.service_name,
            status=request.status,
            requested_by=request.requested_by,
            started_at=request.started_at,
            completed_at=request.completed_at,
            produced_artifact_ids=produced_artifact_ids,
            produced_artifact_counts=produced_artifact_counts,
            storage_locations=request.storage_locations,
            pipeline_event_ids=dedupe_preserve_order(request.pipeline_event_ids),
            alert_record_ids=[alert.alert_record_id for alert in alert_records],
            failure_messages=request.failure_messages,
            attention_reasons=request.attention_reasons,
            notes=request.notes,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="monitoring_run_summary",
                upstream_artifact_ids=dedupe_preserve_order(
                    [
                        request.workflow_run_id,
                        *request.pipeline_event_ids,
                        *produced_artifact_ids,
                        *[alert.alert_record_id for alert in alert_records],
                    ]
                ),
                workflow_run_id=request.workflow_run_id,
                notes=request.notes,
            ),
            created_at=now,
            updated_at=now,
        )
        summary_storage_location = store.persist_model(
            artifact_id=run_summary.run_summary_id,
            category="run_summaries",
            model=run_summary,
            source_reference_ids=run_summary.provenance.source_reference_ids,
        )
        return RecordRunSummaryResponse(
            run_summary=run_summary,
            alert_records=alert_records,
            storage_locations=[
                *condition_storage_locations,
                *alert_storage_locations,
                summary_storage_location,
            ],
        )

    def run_health_checks(
        self,
        request: RunHealthChecksRequest,
    ) -> RunHealthChecksResponse:
        """Evaluate and persist a small set of local health and readiness checks."""

        artifact_root = request.artifact_root or get_settings().resolved_artifact_root
        monitoring_root = request.monitoring_root or (artifact_root / "monitoring")
        review_root = request.review_root or (artifact_root / "review")
        store = LocalMonitoringArtifactStore(root=monitoring_root, clock=self.clock)
        conditions, condition_storage_locations = self._ensure_default_alert_conditions(
            monitoring_root=monitoring_root,
            store=store,
        )
        existing_alerts = self._load_category(
            monitoring_root=monitoring_root,
            category="alert_records",
            model_cls=AlertRecord,
        )
        now = self.clock.now()

        health_checks = [
            self._build_health_check(
                service_name="system",
                check_name="artifact_root_resolved",
                status=(
                    HealthCheckStatus.PASS
                    if artifact_root.is_absolute()
                    else HealthCheckStatus.FAIL
                ),
                message=(
                    f"Artifact root resolved to `{artifact_root}`."
                    if artifact_root.is_absolute()
                    else "Artifact root is not an absolute path."
                ),
                details={"artifact_root": str(artifact_root)},
                checked_at=now,
            ),
            self._build_health_check(
                service_name="monitoring",
                check_name="monitoring_storage_available",
                status=(
                    HealthCheckStatus.PASS
                    if monitoring_root.parent.exists()
                    else HealthCheckStatus.FAIL
                ),
                message=(
                    f"Monitoring root is available under `{monitoring_root}`."
                    if monitoring_root.parent.exists()
                    else "Monitoring root parent directory is not available."
                ),
                details={"monitoring_root": str(monitoring_root)},
                checked_at=now,
            ),
            self._service_registry_health_check(checked_at=now),
            self._build_health_check(
                service_name="operator_review",
                check_name="review_storage_readable",
                status=(
                    HealthCheckStatus.PASS
                    if review_root.exists()
                    else HealthCheckStatus.WARN
                ),
                message=(
                    f"Review artifact root `{review_root}` is readable."
                    if review_root.exists()
                    else "Review artifact root has not been materialized yet."
                ),
                details={"review_root": str(review_root)},
                checked_at=now,
            ),
        ]

        open_alerts = [
            alert
            for alert in existing_alerts
            if alert.state is AlertState.OPEN
        ]
        health_checks.append(
            self._build_health_check(
                service_name="monitoring",
                check_name="recent_open_alerts_present",
                status=(
                    HealthCheckStatus.WARN if open_alerts else HealthCheckStatus.PASS
                ),
                message=(
                    f"{len(open_alerts)} open alerts currently require attention."
                    if open_alerts
                    else "No open alerts are currently recorded."
                ),
                details={"open_alert_count": str(len(open_alerts))},
                checked_at=now,
            )
        )

        storage_locations: list[ArtifactStorageLocation] = list(condition_storage_locations)
        alert_records: list[AlertRecord] = []
        for health_check in health_checks:
            storage_locations.append(
                store.persist_model(
                    artifact_id=health_check.health_check_id,
                    category="health_checks",
                    model=health_check,
                    source_reference_ids=health_check.provenance.source_reference_ids,
                )
            )
            if health_check.status is HealthCheckStatus.FAIL:
                alert_record, alert_storage = self._ensure_alert_record(
                    monitoring_root=monitoring_root,
                    store=store,
                    existing_alerts=existing_alerts,
                    condition=conditions["health_check_failed"],
                    service_name=health_check.service_name,
                    workflow_name=None,
                    workflow_run_id=None,
                    message=health_check.message,
                    related_artifact_ids=[health_check.health_check_id],
                )
                alert_records.append(alert_record)
                if alert_storage is not None:
                    storage_locations.append(alert_storage)

        service_status_response = self.get_service_statuses(
            GetServiceStatusesRequest(
                monitoring_root=monitoring_root,
                limit_recent_runs=request.limit_recent_runs,
            )
        )
        notes = [
            "Day 12 health checks are local and structural only.",
            "No external telemetry or tracing system is implied by these results.",
        ]
        return RunHealthChecksResponse(
            health_checks=health_checks,
            alert_records=alert_records,
            service_statuses=service_status_response.items,
            storage_locations=storage_locations,
            notes=notes,
        )

    def list_recent_run_summaries(
        self,
        request: ListRecentRunSummariesRequest,
    ) -> ListRecentRunSummariesResponse:
        """List recent persisted run summaries."""

        monitoring_root = self._resolve_monitoring_root(request.monitoring_root)
        run_summaries = self._sorted_run_summaries(monitoring_root=monitoring_root)
        if request.service_name is not None:
            run_summaries = [
                summary
                for summary in run_summaries
                if summary.service_name == request.service_name
            ]
        if request.workflow_name is not None:
            run_summaries = [
                summary
                for summary in run_summaries
                if summary.workflow_name == request.workflow_name
            ]
        items = run_summaries[: request.limit]
        return ListRecentRunSummariesResponse(
            items=items,
            total=len(items),
            notes=[],
        )

    def list_recent_failure_summaries(
        self,
        request: ListRecentFailureSummariesRequest,
    ) -> ListRecentFailureSummariesResponse:
        """List recent failed or attention-required summaries and open alerts."""

        monitoring_root = self._resolve_monitoring_root(request.monitoring_root)
        run_summaries = [
            summary
            for summary in self._sorted_run_summaries(monitoring_root=monitoring_root)
            if summary.status in {
                WorkflowStatus.FAILED,
                WorkflowStatus.PARTIAL,
                WorkflowStatus.ATTENTION_REQUIRED,
            }
        ]
        alert_records = [
            alert
            for alert in self._sorted_alert_records(monitoring_root=monitoring_root)
            if alert.state is AlertState.OPEN
        ]
        if request.service_name is not None:
            run_summaries = [
                summary
                for summary in run_summaries
                if summary.service_name == request.service_name
            ]
            alert_records = [
                alert
                for alert in alert_records
                if alert.service_name == request.service_name
            ]
        return ListRecentFailureSummariesResponse(
            run_summaries=run_summaries[: request.limit],
            alert_records=alert_records[: request.limit],
            total_runs=min(len(run_summaries), request.limit),
            total_alerts=min(len(alert_records), request.limit),
            notes=[],
        )

    def get_service_statuses(
        self,
        request: GetServiceStatusesRequest,
    ) -> GetServiceStatusesResponse:
        """Derive current service statuses from health checks, runs, and alerts."""

        monitoring_root = self._resolve_monitoring_root(request.monitoring_root)
        run_summaries = self._sorted_run_summaries(monitoring_root=monitoring_root)
        health_checks = self._sorted_health_checks(monitoring_root=monitoring_root)
        alert_records = self._sorted_alert_records(monitoring_root=monitoring_root)

        from libraries.core.service_registry import build_service_registry

        service_registry = build_service_registry(clock=self.clock)
        items: list[ServiceStatus] = []
        for service_name, service in service_registry.items():
            service_run_summaries = [
                summary
                for summary in run_summaries
                if summary.service_name == service_name
            ][: request.limit_recent_runs]
            service_health_checks = [
                health_check
                for health_check in health_checks
                if health_check.service_name == service_name
            ][: request.limit_recent_runs]
            service_alerts = [
                alert
                for alert in alert_records
                if alert.service_name == service_name and alert.state is AlertState.OPEN
            ]
            timestamps = [
                *[summary.completed_at for summary in service_run_summaries],
                *[health_check.checked_at for health_check in service_health_checks],
                *[alert.triggered_at for alert in service_alerts],
            ]
            notes: list[str] = []
            if not service_run_summaries:
                notes.append("No monitored runs recorded yet.")
            if service_alerts:
                notes.append("Open alerts require attention.")
            items.append(
                ServiceStatus(
                    service_name=service_name,
                    capability_description=service.capability().description,
                    status=derive_service_status(
                        recent_run_summaries=service_run_summaries,
                        recent_health_checks=service_health_checks,
                        open_alerts=service_alerts,
                    ),
                    last_checked_at=max(timestamps) if timestamps else self.clock.now(),
                    recent_run_summary_ids=[
                        summary.run_summary_id for summary in service_run_summaries
                    ],
                    open_alert_count=len(service_alerts),
                    notes=notes,
                )
            )
        return GetServiceStatusesResponse(
            items=sorted(items, key=lambda item: item.service_name),
            total=len(items),
            notes=[],
        )

    def summarize_ablation_monitoring(
        self,
        *,
        evaluation_report: EvaluationReport | None,
        failure_cases: list[FailureCase],
        robustness_checks: list[RobustnessCheck],
    ) -> tuple[WorkflowStatus, list[str]]:
        """Expose a small helper used by the ablation workflow integration."""

        return (
            derive_ablation_run_status(
                evaluation_report=evaluation_report,
                failure_cases=failure_cases,
                robustness_checks=robustness_checks,
            ),
            attention_reasons_from_ablation(
                evaluation_report=evaluation_report,
                failure_cases=failure_cases,
                robustness_checks=robustness_checks,
            ),
        )

    def _resolve_monitoring_root(self, output_root: Path | None) -> Path:
        """Resolve the monitoring artifact root."""

        return output_root or (get_settings().resolved_artifact_root / "monitoring")

    def _ensure_default_alert_conditions(
        self,
        *,
        monitoring_root: Path,
        store: LocalMonitoringArtifactStore,
    ) -> tuple[dict[str, AlertCondition], list[ArtifactStorageLocation]]:
        """Persist the small Day 12 set of built-in alert conditions when missing."""

        existing_conditions = {
            condition.name: condition
            for condition in self._load_category(
                monitoring_root=monitoring_root,
                category="alert_conditions",
                model_cls=AlertCondition,
            )
        }
        storage_locations: list[ArtifactStorageLocation] = []
        definitions = [
            ("workflow_failed", Severity.HIGH, "A monitored workflow raised an exception."),
            (
                "attention_required",
                Severity.MEDIUM,
                "A monitored workflow completed but requires explicit attention.",
            ),
            (
                "zero_outputs_when_outputs_expected",
                Severity.MEDIUM,
                "A workflow completed without producing expected persisted outputs.",
            ),
            ("health_check_failed", Severity.HIGH, "A persisted health check failed."),
        ]
        now = self.clock.now()
        for name, severity, description in definitions:
            if name in existing_conditions:
                continue
            condition = AlertCondition(
                alert_condition_id=make_canonical_id("alertcond", "monitoring", name),
                name=name,
                service_name="monitoring",
                workflow_name=None,
                severity=severity,
                description=description,
                enabled=True,
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="monitoring_default_alert_condition",
                    upstream_artifact_ids=[],
                ),
                created_at=now,
                updated_at=now,
            )
            existing_conditions[name] = condition
            storage_locations.append(
                store.persist_model(
                    artifact_id=condition.alert_condition_id,
                    category="alert_conditions",
                    model=condition,
                    source_reference_ids=condition.provenance.source_reference_ids,
                )
            )
        return existing_conditions, storage_locations

    def _ensure_alert_record(
        self,
        *,
        monitoring_root: Path,
        store: LocalMonitoringArtifactStore,
        existing_alerts: list[AlertRecord],
        condition: AlertCondition,
        service_name: str,
        workflow_name: str | None,
        workflow_run_id: str | None,
        message: str,
        related_artifact_ids: list[str],
    ) -> tuple[AlertRecord, ArtifactStorageLocation | None]:
        """Create or reuse one open alert record."""

        alert_record_id = make_canonical_id(
            "alert",
            condition.alert_condition_id,
            service_name,
            workflow_name or "none",
            workflow_run_id or "none",
            message,
        )
        existing = next(
            (alert for alert in existing_alerts if alert.alert_record_id == alert_record_id),
            None,
        )
        if existing is not None and existing.state is AlertState.OPEN:
            return existing, None

        now = self.clock.now()
        alert_record = AlertRecord(
            alert_record_id=alert_record_id,
            alert_condition_id=condition.alert_condition_id,
            service_name=service_name,
            workflow_name=workflow_name,
            workflow_run_id=workflow_run_id,
            severity=condition.severity,
            state=AlertState.OPEN,
            triggered_at=now,
            message=message,
            related_artifact_ids=dedupe_preserve_order(related_artifact_ids),
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="monitoring_alert_record",
                upstream_artifact_ids=dedupe_preserve_order(related_artifact_ids),
                workflow_run_id=workflow_run_id,
                notes=[f"alert_condition={condition.name}"],
            ),
            created_at=now,
            updated_at=now,
        )
        storage_location = store.persist_model(
            artifact_id=alert_record.alert_record_id,
            category="alert_records",
            model=alert_record,
            source_reference_ids=alert_record.provenance.source_reference_ids,
        )
        return alert_record, storage_location

    def _build_health_check(
        self,
        *,
        service_name: str,
        check_name: str,
        status: HealthCheckStatus,
        message: str,
        details: dict[str, str],
        checked_at: datetime,
    ) -> HealthCheck:
        """Build one persisted health check artifact."""

        return HealthCheck(
            health_check_id=make_canonical_id(
                "hcheck",
                service_name,
                check_name,
                checked_at.isoformat(),
            ),
            service_name=service_name,
            check_name=check_name,
            status=status,
            checked_at=checked_at,
            message=message,
            details=details,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="monitoring_health_check",
                upstream_artifact_ids=[],
            ),
            created_at=checked_at,
            updated_at=checked_at,
        )

    def _service_registry_health_check(self, *, checked_at: datetime) -> HealthCheck:
        """Build the service-registry health check."""

        from libraries.core.service_registry import build_service_registry

        try:
            registry = build_service_registry(clock=self.clock)
            return self._build_health_check(
                service_name="system",
                check_name="service_registry_loaded",
                status=HealthCheckStatus.PASS,
                message=f"Service registry loaded with {len(registry)} services.",
                details={"service_count": str(len(registry))},
                checked_at=checked_at,
            )
        except Exception as exc:
            return self._build_health_check(
                service_name="system",
                check_name="service_registry_loaded",
                status=HealthCheckStatus.FAIL,
                message=f"Service registry failed to load: {exc}",
                details={"error": str(exc)},
                checked_at=checked_at,
            )

    def _load_category(
        self,
        *,
        monitoring_root: Path,
        category: str,
        model_cls: type[TModel],
    ) -> list[TModel]:
        """Load one monitoring artifact category."""

        return load_models(root=monitoring_root, category=category, model_cls=model_cls)

    def _sorted_run_summaries(self, *, monitoring_root: Path) -> list[RunSummary]:
        """Load run summaries ordered from most recent to oldest."""

        return sorted(
            self._load_category(
                monitoring_root=monitoring_root,
                category="run_summaries",
                model_cls=RunSummary,
            ),
            key=lambda summary: summary.completed_at,
            reverse=True,
        )

    def _sorted_alert_records(self, *, monitoring_root: Path) -> list[AlertRecord]:
        """Load alert records ordered from most recent to oldest."""

        return sorted(
            self._load_category(
                monitoring_root=monitoring_root,
                category="alert_records",
                model_cls=AlertRecord,
            ),
            key=lambda alert: alert.triggered_at,
            reverse=True,
        )

    def _sorted_health_checks(self, *, monitoring_root: Path) -> list[HealthCheck]:
        """Load health checks ordered from most recent to oldest."""

        return sorted(
            self._load_category(
                monitoring_root=monitoring_root,
                category="health_checks",
                model_cls=HealthCheck,
            ),
            key=lambda health_check: health_check.checked_at,
            reverse=True,
        )
