from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generic, Literal, TypeVar

from pydantic import Field, model_validator

from libraries.schemas.base import StrictModel
from libraries.schemas.storage import ArtifactStorageLocation
from libraries.schemas.system import HealthCheckStatus, WorkflowStatus

TData = TypeVar("TData")


class InterfaceWarning(StrictModel):
    """Structured interface-layer warning preserved for operators and demos."""

    warning_code: str = Field(description="Stable warning code.")
    message: str = Field(description="Human-readable warning message.")
    scope: str | None = Field(default=None, description="Optional scope such as `demo` or `api`.")
    related_ids: list[str] = Field(
        default_factory=list,
        description="Optional related artifact, route, or workflow identifiers.",
    )

    @model_validator(mode="after")
    def validate_warning(self) -> InterfaceWarning:
        """Require non-empty warning identifiers and messages."""

        if not self.warning_code:
            raise ValueError("warning_code must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class APIResponseEnvelope(StrictModel, Generic[TData]):
    """Consistent success envelope for API and CLI-facing read models."""

    status: Literal["ok"] = Field(default="ok", description="Successful interface status.")
    data: TData = Field(description="Typed response payload.")
    warnings: list[InterfaceWarning] = Field(
        default_factory=list,
        description="Visible interface-layer warnings preserved with the payload.",
    )
    notes: list[str] = Field(default_factory=list, description="Human-readable response notes.")
    generated_at: datetime = Field(description="UTC timestamp when the response was generated.")


class ErrorResponse(StrictModel):
    """Consistent non-success API response payload."""

    status: Literal["error"] = Field(default="error", description="Error response status.")
    error_code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable error summary.")
    details: list[str] = Field(
        default_factory=list,
        description="Structured detail rows explaining validation or resolution failures.",
    )
    path: str = Field(description="Request path that produced the error.")
    timestamp: datetime = Field(description="UTC timestamp when the error response was generated.")

    @model_validator(mode="after")
    def validate_error(self) -> ErrorResponse:
        """Require non-empty error identifiers and path data."""

        if not self.error_code:
            raise ValueError("error_code must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        if not self.path:
            raise ValueError("path must be non-empty.")
        return self


class CapabilityDescriptor(StrictModel):
    """Normalized description of one exposed service, agent, or workflow capability."""

    name: str = Field(description="Stable capability name.")
    kind: Literal["service", "agent", "workflow"] = Field(
        description="Capability category."
    )
    description: str = Field(description="Human-readable capability description.")
    inputs: list[str] = Field(default_factory=list, description="Primary input types.")
    outputs: list[str] = Field(default_factory=list, description="Primary output types.")
    api_routes: list[str] = Field(default_factory=list, description="Canonical API routes.")
    cli_commands: list[str] = Field(
        default_factory=list,
        description="Supported CLI commands for the capability.",
    )
    config_keys: list[str] = Field(
        default_factory=list,
        description="Relevant environment or settings keys.",
    )
    notes: list[str] = Field(default_factory=list, description="Capability-specific caveats.")

    @model_validator(mode="after")
    def validate_capability(self) -> CapabilityDescriptor:
        """Require non-empty names and descriptions."""

        if not self.name:
            raise ValueError("name must be non-empty.")
        if not self.description:
            raise ValueError("description must be non-empty.")
        return self


class WorkflowInvocationResult(StrictModel):
    """Compact interface-level summary of one workflow invocation."""

    workflow_name: str = Field(description="Workflow name.")
    invocation_kind: Literal["api", "cli"] = Field(
        description="Which interface surface invoked the workflow."
    )
    workflow_run_id: str = Field(description="Stable workflow run identifier.")
    status: WorkflowStatus = Field(description="Observed workflow status.")
    artifact_root: Path = Field(description="Primary artifact root used by the workflow.")
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Storage locations written by the workflow or wrapper.",
    )
    produced_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Material artifact identifiers produced by the workflow.",
    )
    run_summary_ids: list[str] = Field(
        default_factory=list,
        description="Related monitoring run-summary identifiers when available.",
    )
    notes: list[str] = Field(default_factory=list, description="Workflow invocation notes.")
    warnings: list[InterfaceWarning] = Field(
        default_factory=list,
        description="Interface-level warnings attached to the invocation.",
    )

    @model_validator(mode="after")
    def validate_workflow_invocation(self) -> WorkflowInvocationResult:
        """Require non-empty workflow identifiers."""

        if not self.workflow_name:
            raise ValueError("workflow_name must be non-empty.")
        if not self.workflow_run_id:
            raise ValueError("workflow_run_id must be non-empty.")
        return self


class DemoRunResult(WorkflowInvocationResult):
    """Compact interface-level summary of one end-to-end demo run."""

    demo_run_id: str = Field(description="Stable demo run identifier.")
    manifest_path: Path = Field(description="Path to the persisted demo manifest.")
    company_id: str = Field(description="Covered company identifier.")
    portfolio_proposal_id: str | None = Field(
        default=None,
        description="Final portfolio proposal identifier when available.",
    )
    review_queue_total: int = Field(description="Count of review queue items after the demo.")
    paper_trade_candidate_count: int = Field(
        description="Count of paper-trade candidates created by the demo."
    )
    health_status: HealthCheckStatus = Field(
        description="Overall health outcome observed after the demo run."
    )

    @model_validator(mode="after")
    def validate_demo_run(self) -> DemoRunResult:
        """Require non-empty demo identifiers."""

        if not self.demo_run_id:
            raise ValueError("demo_run_id must be non-empty.")
        if not self.company_id:
            raise ValueError("company_id must be non-empty.")
        return self


class ServiceManifest(StrictModel):
    """Grounded interface manifest for the current local repo surface."""

    project_name: str = Field(description="Configured project name.")
    environment: str = Field(description="Current runtime environment.")
    artifact_root: Path = Field(description="Resolved local artifact root.")
    generated_at: datetime = Field(description="UTC timestamp when the manifest was generated.")
    capabilities: list[CapabilityDescriptor] = Field(
        default_factory=list,
        description="Visible services, agents, and workflow descriptors.",
    )
    config_surface: dict[str, str] = Field(
        default_factory=dict,
        description="Inspectable runtime configuration key-value surface.",
    )
    warnings: list[InterfaceWarning] = Field(
        default_factory=list,
        description="Visible limitations for the current local interface surface.",
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> ServiceManifest:
        """Require non-empty project metadata."""

        if not self.project_name:
            raise ValueError("project_name must be non-empty.")
        if not self.environment:
            raise ValueError("environment must be non-empty.")
        return self
