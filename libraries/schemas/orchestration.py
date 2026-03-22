from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, StrictModel, TimestampedModel
from libraries.schemas.research import AblationView
from libraries.schemas.system import WorkflowStatus


class ScheduleMode(StrEnum):
    """Local scheduling mode for an orchestration configuration."""

    MANUAL_LOCAL = "manual_local"
    DAILY_LOCAL = "daily_local"


class DataRefreshMode(StrEnum):
    """How the daily workflow should source its upstream ingestion state."""

    FIXTURE_REFRESH = "fixture_refresh"
    REUSE_EXISTING_INGESTION = "reuse_existing_ingestion"


class RunFailureAction(StrEnum):
    """What the orchestration layer should do after a step failure."""

    FAIL_WORKFLOW = "fail_workflow"
    ATTENTION_REQUIRED_STOP = "attention_required_stop"
    PARTIAL_CONTINUE = "partial_continue"


class RetryPolicy(StrictModel):
    """Explicit retry policy for one orchestration step."""

    max_attempts: int = Field(ge=1, description="Maximum attempts including the first run.")
    automatic_retry_enabled: bool = Field(
        description="Whether the orchestration layer may retry the step automatically."
    )
    backoff_seconds: int = Field(
        default=0,
        ge=0,
        description="Delay between attempts for local retries.",
    )
    retryable: bool = Field(description="Whether the step is retryable at all.")

    @model_validator(mode="after")
    def validate_retry_policy(self) -> RetryPolicy:
        """Keep retry semantics explicit and internally coherent."""

        if not self.retryable and self.automatic_retry_enabled:
            raise ValueError("automatic_retry_enabled requires retryable=True.")
        if not self.retryable and self.max_attempts != 1:
            raise ValueError("Non-retryable steps must use max_attempts=1.")
        if self.automatic_retry_enabled and self.max_attempts < 2:
            raise ValueError("Automatic retries require max_attempts of at least 2.")
        return self


class ManualInterventionRequirement(StrictModel):
    """Explicit human review or operator action requirement."""

    gate_reason: str = Field(description="Short reason why a human action is required.")
    blocking: bool = Field(description="Whether this requirement blocks autonomous progression.")
    required_role: str = Field(description="Operator role expected to resolve the requirement.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts the operator should inspect before acting.",
    )
    operator_instructions: list[str] = Field(
        default_factory=list,
        description="Concrete instructions for the operator.",
    )

    @model_validator(mode="after")
    def validate_manual_intervention(self) -> ManualInterventionRequirement:
        """Require a visible reason and instructions for manual stops."""

        if not self.gate_reason:
            raise ValueError("gate_reason must be non-empty.")
        if not self.required_role:
            raise ValueError("required_role must be non-empty.")
        if not self.operator_instructions:
            raise ValueError("operator_instructions must contain at least one instruction.")
        return self


class WorkflowStepDefinition(StrictModel):
    """Code-owned step definition used by a workflow definition."""

    step_name: str = Field(description="Stable orchestration step name.")
    sequence_index: int = Field(ge=1, description="1-based workflow sequence index.")
    dependency_step_names: list[str] = Field(
        default_factory=list,
        description="Upstream step names that must complete before this step runs.",
    )
    owning_service: str = Field(description="Service or pipeline responsible for the step.")
    description: str = Field(description="Short explanation of the step purpose.")
    retry_policy: RetryPolicy = Field(description="Retry policy for this step.")
    failure_action: RunFailureAction = Field(
        description="Failure action to apply when the step exhausts retries."
    )
    manual_review_gate: bool = Field(
        default=False,
        description="Whether the step normally includes an explicit human review gate.",
    )

    @model_validator(mode="after")
    def validate_step_definition(self) -> WorkflowStepDefinition:
        """Require stable names and visible descriptions."""

        if not self.step_name:
            raise ValueError("step_name must be non-empty.")
        if not self.owning_service:
            raise ValueError("owning_service must be non-empty.")
        if not self.description:
            raise ValueError("description must be non-empty.")
        if self.step_name in self.dependency_step_names:
            raise ValueError("A step cannot depend on itself.")
        return self


class WorkflowDefinition(TimestampedModel):
    """Persisted definition of one local orchestration workflow."""

    workflow_definition_id: str = Field(description="Canonical workflow-definition identifier.")
    workflow_name: str = Field(description="Stable workflow name.")
    description: str = Field(description="Human-readable workflow description.")
    step_definitions: list[WorkflowStepDefinition] = Field(
        default_factory=list,
        description="Ordered step definitions for the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Workflow-level notes describing scope or limitations.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the workflow definition.")

    @model_validator(mode="after")
    def validate_workflow_definition(self) -> WorkflowDefinition:
        """Require a non-empty ordered step sequence with unique step names."""

        if not self.workflow_name:
            raise ValueError("workflow_name must be non-empty.")
        if not self.description:
            raise ValueError("description must be non-empty.")
        if not self.step_definitions:
            raise ValueError("step_definitions must contain at least one step.")
        seen_names: set[str] = set()
        expected_sequence = list(range(1, len(self.step_definitions) + 1))
        actual_sequence = [step.sequence_index for step in self.step_definitions]
        if actual_sequence != expected_sequence:
            raise ValueError("step_definitions must use consecutive 1-based sequence_index values.")
        for step in self.step_definitions:
            if step.step_name in seen_names:
                raise ValueError("step_definitions must use unique step_name values.")
            seen_names.add(step.step_name)
        return self


class ScheduledRunConfig(TimestampedModel):
    """Persisted local run configuration for one workflow definition."""

    scheduled_run_config_id: str = Field(description="Canonical scheduled-run identifier.")
    workflow_definition_id: str = Field(description="Linked workflow-definition identifier.")
    schedule_mode: ScheduleMode = Field(description="Local scheduling mode for the workflow.")
    enabled: bool = Field(description="Whether the local configuration is active.")
    artifact_roots: dict[str, Path] = Field(
        default_factory=dict,
        description="Named artifact roots used by the orchestration layer.",
    )
    default_requester: str = Field(description="Default requester recorded for the local run.")
    data_refresh_mode: DataRefreshMode = Field(
        description="Default data refresh mode for the run."
    )
    company_id: str | None = Field(
        default=None,
        description="Optional default company slice for local deterministic runs.",
    )
    fixtures_root: Path | None = Field(
        default=None,
        description="Optional default fixture root for local refreshes.",
    )
    ablation_view: AblationView = Field(
        description="Default signal-view slice used by the daily workflow."
    )
    assumed_reference_prices: dict[str, float] = Field(
        default_factory=dict,
        description="Optional default price assumptions for paper-trade candidate sizing.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the scheduled-run config.")

    @model_validator(mode="after")
    def validate_scheduled_run_config(self) -> ScheduledRunConfig:
        """Require explicit roots and a visible default requester."""

        if not self.workflow_definition_id:
            raise ValueError("workflow_definition_id must be non-empty.")
        if not self.artifact_roots:
            raise ValueError("artifact_roots must contain at least one named root.")
        if not self.default_requester:
            raise ValueError("default_requester must be non-empty.")
        if any(price <= 0.0 for price in self.assumed_reference_prices.values()):
            raise ValueError("assumed_reference_prices values must be positive.")
        return self


class RunbookEntry(TimestampedModel):
    """Operator-facing runbook guidance for one orchestration step."""

    runbook_entry_id: str = Field(description="Canonical runbook-entry identifier.")
    step_name: str = Field(description="Stable step name covered by the entry.")
    purpose: str = Field(description="Why this step exists.")
    expected_outputs: list[str] = Field(
        default_factory=list,
        description="Artifacts or outcomes the operator should expect.",
    )
    operator_checks: list[str] = Field(
        default_factory=list,
        description="Concrete operator checks to perform for the step.",
    )
    failure_triage_instructions: list[str] = Field(
        default_factory=list,
        description="Instructions for triaging failures in this step.",
    )
    manual_review_required: bool = Field(
        default=False,
        description="Whether the step normally requires human review or approval.",
    )
    next_manual_action: str | None = Field(
        default=None,
        description="Concrete next operator action when manual review is required.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the runbook entry.")

    @model_validator(mode="after")
    def validate_runbook_entry(self) -> RunbookEntry:
        """Require visible purpose, checks, and failure guidance."""

        if not self.step_name:
            raise ValueError("step_name must be non-empty.")
        if not self.purpose:
            raise ValueError("purpose must be non-empty.")
        if not self.expected_outputs:
            raise ValueError("expected_outputs must contain at least one item.")
        if not self.operator_checks:
            raise ValueError("operator_checks must contain at least one item.")
        if not self.failure_triage_instructions:
            raise ValueError("failure_triage_instructions must contain at least one item.")
        if self.manual_review_required and not self.next_manual_action:
            raise ValueError(
                "next_manual_action is required when manual_review_required is True."
            )
        return self


class RunStep(TimestampedModel):
    """Inspectable execution state for one orchestration step."""

    run_step_id: str = Field(description="Canonical run-step identifier.")
    workflow_execution_id: str = Field(description="Parent workflow-execution identifier.")
    step_name: str = Field(description="Stable step name.")
    sequence_index: int = Field(ge=1, description="1-based step sequence index.")
    dependency_step_ids: list[str] = Field(
        default_factory=list,
        description="Resolved upstream run-step identifiers for this step.",
    )
    owning_service: str = Field(description="Service or pipeline responsible for the step.")
    status: WorkflowStatus = Field(description="Current status of the step.")
    attempt_count: int = Field(ge=0, description="Attempt count for the step so far.")
    retry_policy: RetryPolicy = Field(description="Retry policy applied to the step.")
    failure_action: RunFailureAction = Field(
        description="Failure action applied if the step exhausts retries."
    )
    child_workflow_ids: list[str] = Field(
        default_factory=list,
        description="Underlying workflow or service run identifiers triggered by the step.",
    )
    child_run_summary_ids: list[str] = Field(
        default_factory=list,
        description="Linked monitoring run-summary identifiers for child workflows.",
    )
    produced_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts materially produced by the step.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Step-level operational notes.",
    )
    manual_intervention_requirement: ManualInterventionRequirement | None = Field(
        default=None,
        description="Explicit manual gate requirement when the step stops for review.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the step started running.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the step completed or stopped.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the run step.")

    @model_validator(mode="after")
    def validate_run_step(self) -> RunStep:
        """Require explicit linkage and ordered optional timestamps."""

        if not self.workflow_execution_id:
            raise ValueError("workflow_execution_id must be non-empty.")
        if not self.step_name:
            raise ValueError("step_name must be non-empty.")
        if not self.owning_service:
            raise ValueError("owning_service must be non-empty.")
        if self.completed_at is not None:
            if self.started_at is None:
                raise ValueError("started_at is required when completed_at is provided.")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at must be greater than or equal to started_at.")
        return self


class WorkflowExecution(TimestampedModel):
    """Top-level persisted execution record for one local orchestration run."""

    workflow_execution_id: str = Field(description="Canonical workflow-execution identifier.")
    workflow_definition_id: str = Field(description="Linked workflow-definition identifier.")
    scheduled_run_config_id: str = Field(description="Linked scheduled-run-config identifier.")
    status: WorkflowStatus = Field(description="Current or terminal workflow status.")
    step_ids: list[str] = Field(
        default_factory=list,
        description="Ordered run-step identifiers in this execution.",
    )
    linked_child_run_summary_ids: list[str] = Field(
        default_factory=list,
        description="Monitoring run summaries produced by child workflows.",
    )
    produced_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts materially produced by the workflow.",
    )
    started_at: datetime = Field(description="UTC timestamp when the workflow execution started.")
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the workflow execution completed or stopped.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Workflow-level operational notes.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the workflow execution.")

    @model_validator(mode="after")
    def validate_workflow_execution(self) -> WorkflowExecution:
        """Require explicit linkage and ordered completion time when present."""

        if not self.workflow_definition_id:
            raise ValueError("workflow_definition_id must be non-empty.")
        if not self.scheduled_run_config_id:
            raise ValueError("scheduled_run_config_id must be non-empty.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at.")
        return self
