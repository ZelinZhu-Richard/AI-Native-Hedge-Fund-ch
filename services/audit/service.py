from __future__ import annotations

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import AuditOutcome, ProvenanceRecord, StrictModel
from libraries.schemas.system import AuditLog
from libraries.time import utc_now
from libraries.utils import make_prefixed_id


class AuditEventRequest(StrictModel):
    """Request to record a material system or human action."""

    event_type: str = Field(description="Normalized event type.")
    actor_type: str = Field(description="Actor category.")
    actor_id: str = Field(description="Actor identifier.")
    target_type: str = Field(description="Target entity type.")
    target_id: str = Field(description="Target entity identifier.")
    action: str = Field(description="Action taken.")
    reason: str | None = Field(default=None, description="Reason for the action if provided.")
    request_id: str | None = Field(default=None, description="Request trace identifier.")


class AuditEventResponse(StrictModel):
    """Response containing the recorded audit event."""

    audit_log: AuditLog = Field(description="Recorded audit log artifact.")


class AuditLoggingService(BaseService):
    """Record auditable events independently of business services."""

    capability_name = "audit"
    capability_description = "Records immutable audit events for critical actions and decisions."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["material actions"],
            produces=["AuditLog"],
            api_routes=[],
        )

    def record_event(self, request: AuditEventRequest) -> AuditEventResponse:
        """Create a placeholder audit log record."""

        now = utc_now()
        event = AuditLog(
            audit_log_id=make_prefixed_id("audit"),
            event_type=request.event_type,
            actor_type=request.actor_type,
            actor_id=request.actor_id,
            target_type=request.target_type,
            target_id=request.target_id,
            action=request.action,
            outcome=AuditOutcome.SUCCESS,
            occurred_at=now,
            reason=request.reason,
            request_id=request.request_id,
            related_artifact_ids=[request.target_id],
            provenance=ProvenanceRecord(
                transformation_name="audit_logging_stub",
                transformation_version="day1",
                processing_time=now,
            ),
            created_at=now,
            updated_at=now,
        )
        return AuditEventResponse(audit_log=event)
