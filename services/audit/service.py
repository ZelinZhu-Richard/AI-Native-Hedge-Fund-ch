from __future__ import annotations

from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import ArtifactStorageLocation, AuditOutcome, StrictModel
from libraries.schemas.system import AuditLog
from libraries.utils import make_prefixed_id
from services.audit.storage import LocalAuditArtifactStore


class AuditEventRequest(StrictModel):
    """Request to record a material system or human action."""

    event_type: str = Field(description="Normalized event type.")
    actor_type: str = Field(description="Actor category.")
    actor_id: str = Field(description="Actor identifier.")
    target_type: str = Field(description="Target entity type.")
    target_id: str = Field(description="Target entity identifier.")
    action: str = Field(description="Action taken.")
    outcome: AuditOutcome = Field(
        default=AuditOutcome.SUCCESS,
        description="Outcome classification for the audited action.",
    )
    reason: str | None = Field(default=None, description="Reason for the action if provided.")
    request_id: str | None = Field(default=None, description="Request trace identifier.")
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
        description="Additional artifact identifiers associated with the event.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Free-form notes or workflow context for the audited action.",
    )


class AuditEventResponse(StrictModel):
    """Response containing the recorded audit event."""

    audit_log: AuditLog = Field(description="Recorded audit log artifact.")
    storage_location: ArtifactStorageLocation = Field(
        description="Local storage metadata for the persisted audit event."
    )


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

    def record_event(
        self,
        request: AuditEventRequest,
        *,
        output_root: Path | None = None,
    ) -> AuditEventResponse:
        """Create and persist an audit log record."""

        now = self.clock.now()
        related_artifact_ids = list(
            dict.fromkeys([request.target_id, *request.related_artifact_ids])
        )
        event = AuditLog(
            audit_log_id=make_prefixed_id("audit"),
            event_type=request.event_type,
            actor_type=request.actor_type,
            actor_id=request.actor_id,
            target_type=request.target_type,
            target_id=request.target_id,
            action=request.action,
            outcome=request.outcome,
            occurred_at=now,
            reason=request.reason,
            request_id=request.request_id,
            status_before=request.status_before,
            status_after=request.status_after,
            related_artifact_ids=related_artifact_ids,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="audit_logging_service",
                upstream_artifact_ids=related_artifact_ids,
                notes=request.notes,
            ),
            created_at=now,
            updated_at=now,
        )
        store = LocalAuditArtifactStore(
            root=output_root or (get_settings().resolved_artifact_root / "audit"),
            clock=self.clock,
        )
        storage_location = store.persist_model(
            artifact_id=event.audit_log_id,
            category="audit_logs",
            model=event,
            source_reference_ids=event.provenance.source_reference_ids,
        )
        return AuditEventResponse(audit_log=event, storage_location=storage_location)
