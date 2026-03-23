from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from apps.api.builders import (
    build_capability_descriptors,
    build_response_envelope,
    build_service_manifest,
    default_interface_warnings,
)
from apps.api.contracts import (
    CapabilityListPayload,
    HealthDetailsPayload,
    HealthPayload,
    VersionPayload,
)
from apps.api.state import api_clock, service_registry
from libraries.config import get_settings
from libraries.schemas import APIResponseEnvelope, HealthCheckStatus, ServiceManifest
from libraries.time import isoformat_z
from services.monitoring import MonitoringService, RunHealthChecksRequest

router = APIRouter(tags=["system"])


@router.get("/system/health", response_model=APIResponseEnvelope[HealthPayload])
@router.get("/health", response_model=APIResponseEnvelope[HealthPayload], include_in_schema=False)
def health() -> APIResponseEnvelope[HealthPayload]:
    """Return a simple health response."""

    return build_response_envelope(
        data=HealthPayload(status="ok", timestamp=isoformat_z(api_clock.now())),
        generated_at=api_clock.now(),
    )


@router.get("/system/health/details", response_model=APIResponseEnvelope[HealthDetailsPayload])
@router.get(
    "/health/details",
    response_model=APIResponseEnvelope[HealthDetailsPayload],
    include_in_schema=False,
)
def health_details() -> APIResponseEnvelope[HealthDetailsPayload]:
    """Return structured local health and readiness information."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.run_health_checks(RunHealthChecksRequest())
    status = _status_from_health_checks(response.health_checks)
    return build_response_envelope(
        data=HealthDetailsPayload(
            status=status,
            timestamp=isoformat_z(api_clock.now()),
            health_checks=response.health_checks,
            service_statuses=response.service_statuses,
            open_alert_count=sum(item.open_alert_count for item in response.service_statuses),
        ),
        generated_at=api_clock.now(),
        notes=response.notes,
    )


@router.get("/system/version", response_model=APIResponseEnvelope[VersionPayload])
@router.get("/version", response_model=APIResponseEnvelope[VersionPayload], include_in_schema=False)
def version() -> APIResponseEnvelope[VersionPayload]:
    """Return project version metadata."""

    runtime_settings = get_settings()
    return build_response_envelope(
        data=VersionPayload(
            project_name=runtime_settings.project_name,
            version=runtime_settings.app_version,
            environment=runtime_settings.environment,
        ),
        generated_at=api_clock.now(),
    )


@router.get("/system/capabilities", response_model=APIResponseEnvelope[CapabilityListPayload])
@router.get(
    "/capabilities",
    response_model=APIResponseEnvelope[CapabilityListPayload],
    include_in_schema=False,
)
def capabilities() -> APIResponseEnvelope[CapabilityListPayload]:
    """Return normalized services, agents, and workflow descriptors."""

    descriptors = build_capability_descriptors(
        service_capabilities=[service.capability() for service in service_registry.values()]
    )
    return build_response_envelope(
        data=CapabilityListPayload(items=descriptors, total=len(descriptors)),
        generated_at=api_clock.now(),
        warnings=default_interface_warnings(),
    )


@router.get("/system/manifest", response_model=APIResponseEnvelope[ServiceManifest])
def manifest() -> APIResponseEnvelope[ServiceManifest]:
    """Return the grounded interface manifest for the local repo surface."""

    payload = build_service_manifest(
        generated_at=api_clock.now(),
        service_capabilities=[service.capability() for service in service_registry.values()],
    )
    return build_response_envelope(
        data=payload,
        generated_at=api_clock.now(),
        warnings=payload.warnings,
    )


def _status_from_health_checks(health_checks: Sequence[object]) -> str:
    statuses = [check.status for check in health_checks if hasattr(check, "status")]
    if any(status is HealthCheckStatus.FAIL for status in statuses):
        return "fail"
    if any(status is HealthCheckStatus.WARN for status in statuses):
        return "warn"
    return "ok"
