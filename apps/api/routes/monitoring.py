from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api.builders import build_response_envelope
from apps.api.contracts import (
    FailureSummaryPayload,
    RunSummaryListPayload,
    ServiceStatusListPayload,
)
from apps.api.state import api_clock, service_registry
from libraries.schemas import APIResponseEnvelope
from services.monitoring import (
    GetServiceStatusesRequest,
    ListRecentFailureSummariesRequest,
    ListRecentRunSummariesRequest,
    MonitoringService,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/run-summaries/recent", response_model=APIResponseEnvelope[RunSummaryListPayload])
def list_recent_run_summaries(
    service_name: str | None = None,
    workflow_name: str | None = None,
    limit: int = Query(default=20, ge=1, le=200),
) -> APIResponseEnvelope[RunSummaryListPayload]:
    """Return recent persisted monitoring run summaries."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.list_recent_run_summaries(
        ListRecentRunSummariesRequest(
            service_name=service_name,
            workflow_name=workflow_name,
            limit=limit,
        )
    )
    return build_response_envelope(
        data=RunSummaryListPayload(items=response.items, total=response.total),
        generated_at=api_clock.now(),
        notes=response.notes,
    )


@router.get("/failures/recent", response_model=APIResponseEnvelope[FailureSummaryPayload])
def list_recent_failure_summaries(
    service_name: str | None = None,
    limit: int = Query(default=20, ge=1, le=200),
) -> APIResponseEnvelope[FailureSummaryPayload]:
    """Return recent failed or attention-required runs and open alerts."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.list_recent_failure_summaries(
        ListRecentFailureSummariesRequest(
            service_name=service_name,
            limit=limit,
        )
    )
    return build_response_envelope(
        data=FailureSummaryPayload(
            run_summaries=response.run_summaries,
            alert_records=response.alert_records,
            total_runs=response.total_runs,
            total_alerts=response.total_alerts,
        ),
        generated_at=api_clock.now(),
        notes=response.notes,
    )


@router.get("/services", response_model=APIResponseEnvelope[ServiceStatusListPayload])
def list_service_statuses() -> APIResponseEnvelope[ServiceStatusListPayload]:
    """Return derived current statuses for registered services."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.get_service_statuses(GetServiceStatusesRequest())
    return build_response_envelope(
        data=ServiceStatusListPayload(items=response.items, total=response.total),
        generated_at=api_clock.now(),
        notes=response.notes,
    )
