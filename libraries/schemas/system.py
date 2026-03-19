from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.schemas.base import AuditOutcome, ProvenanceRecord, TimestampedModel


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
