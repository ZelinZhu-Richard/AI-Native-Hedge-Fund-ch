from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    AlertCondition,
    AlertRecord,
    AlertState,
    ArtifactStorageLocation,
    DataLayer,
    HealthCheck,
    HealthCheckStatus,
    PipelineEvent,
    PipelineEventType,
    ProvenanceRecord,
    RunSummary,
    ServiceStatus,
    Severity,
    StorageKind,
    WorkflowStatus,
)

FIXED_NOW = datetime(2026, 3, 19, 10, 0, tzinfo=UTC)


def test_run_summary_and_service_status_validate() -> None:
    storage_location = _storage_location()
    run_summary = RunSummary(
        run_summary_id="runsum_test",
        workflow_name="fixture_ingestion",
        workflow_run_id="ingest_test",
        service_name="ingestion",
        status=WorkflowStatus.SUCCEEDED,
        requested_by="unit_test",
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW,
        produced_artifact_ids=["src_test"],
        produced_artifact_counts={"source_references": 1},
        storage_locations=[storage_location],
        pipeline_event_ids=["pevt_test"],
        alert_record_ids=[],
        failure_messages=[],
        attention_reasons=[],
        notes=["note"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    service_status = ServiceStatus(
        service_name="ingestion",
        capability_description="Registers fixtures.",
        status=HealthCheckStatus.PASS,
        last_checked_at=FIXED_NOW,
        recent_run_summary_ids=[run_summary.run_summary_id],
        open_alert_count=0,
        notes=[],
    )
    pipeline_event = PipelineEvent(
        pipeline_event_id="pevt_test",
        workflow_name="fixture_ingestion",
        workflow_run_id="ingest_test",
        service_name="ingestion",
        event_type=PipelineEventType.RUN_COMPLETED,
        status=WorkflowStatus.SUCCEEDED,
        occurred_at=FIXED_NOW,
        message="Completed.",
        related_artifact_ids=["src_test"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    health_check = HealthCheck(
        health_check_id="hcheck_test",
        service_name="monitoring",
        check_name="artifact_root_resolved",
        status=HealthCheckStatus.PASS,
        checked_at=FIXED_NOW,
        message="Artifact root resolved.",
        details={"artifact_root": "/tmp/artifacts"},
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    alert_condition = AlertCondition(
        alert_condition_id="alertcond_test",
        name="workflow_failed",
        service_name="monitoring",
        severity=Severity.HIGH,
        description="Workflow failed.",
        enabled=True,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    alert_record = AlertRecord(
        alert_record_id="alert_test",
        alert_condition_id=alert_condition.alert_condition_id,
        service_name="ingestion",
        workflow_name="fixture_ingestion",
        workflow_run_id="ingest_test",
        severity=Severity.HIGH,
        state=AlertState.OPEN,
        triggered_at=FIXED_NOW,
        message="Fixture ingestion failed.",
        related_artifact_ids=["ingest_test"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert run_summary.produced_artifact_counts["source_references"] == 1
    assert service_status.status is HealthCheckStatus.PASS
    assert pipeline_event.event_type is PipelineEventType.RUN_COMPLETED
    assert health_check.status is HealthCheckStatus.PASS
    assert alert_record.alert_condition_id == alert_condition.alert_condition_id


def test_run_summary_rejects_reverse_time_order() -> None:
    with pytest.raises(ValidationError):
        RunSummary(
            run_summary_id="runsum_test",
            workflow_name="fixture_ingestion",
            workflow_run_id="ingest_test",
            service_name="ingestion",
            status=WorkflowStatus.SUCCEEDED,
            requested_by="unit_test",
            started_at=FIXED_NOW,
            completed_at=datetime(2026, 3, 19, 9, 0, tzinfo=UTC),
            produced_artifact_ids=[],
            produced_artifact_counts={},
            storage_locations=[],
            pipeline_event_ids=[],
            alert_record_ids=[],
            failure_messages=[],
            attention_reasons=[],
            notes=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_alert_record_requires_condition_link() -> None:
    with pytest.raises(ValidationError):
        AlertRecord(
            # type: ignore[call-arg]
            alert_record_id="alert_test",
            service_name="ingestion",
            severity=Severity.HIGH,
            state=AlertState.OPEN,
            triggered_at=FIXED_NOW,
            message="Missing condition link.",
            related_artifact_ids=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def _storage_location() -> ArtifactStorageLocation:
    return ArtifactStorageLocation(
        artifact_storage_location_id="store_test",
        artifact_id="src_test",
        storage_kind=StorageKind.LOCAL_FILESYSTEM,
        data_layer=DataLayer.DERIVED,
        uri="file:///tmp/artifacts/source_references/src_test.json",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
