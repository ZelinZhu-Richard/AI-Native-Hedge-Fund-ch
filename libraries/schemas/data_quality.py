from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, TimestampedModel


class QualitySeverity(StrEnum):
    """Severity level for a data-quality issue or contract breach."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class QualityDecision(StrEnum):
    """Decision taken by a validation gate."""

    PASS = "pass"
    WARN = "warn"
    REFUSE = "refuse"
    QUARANTINE = "quarantine"


class RefusalReason(StrEnum):
    """Stable refusal or quarantine reasons recorded by the quality layer."""

    MISSING_REQUIRED_TIMESTAMP = "missing_required_timestamp"
    MISSING_PROVENANCE = "missing_provenance"
    MISSING_ENTITY_LINKAGE = "missing_entity_linkage"
    INVALID_REVIEW_STATE = "invalid_review_state"
    BROKEN_SIGNAL_LINEAGE = "broken_signal_lineage"
    INCOMPLETE_EXPERIMENT_METADATA = "incomplete_experiment_metadata"
    MISSING_REQUIRED_ARTIFACT = "missing_required_artifact"
    STRUCTURALLY_INVALID_OUTPUT = "structurally_invalid_output"


class DataQualityIssue(TimestampedModel):
    """One structured non-silent issue observed during a quality check."""

    data_quality_issue_id: str = Field(description="Canonical data-quality issue identifier.")
    check_name: str = Field(description="Human-readable name of the producing check.")
    check_code: str = Field(description="Stable code for the producing check.")
    target_type: str = Field(description="Artifact or input type affected by the issue.")
    target_id: str = Field(description="Artifact or input identifier affected by the issue.")
    workflow_name: str | None = Field(
        default=None,
        description="Workflow name when the issue is tied to one workflow boundary.",
    )
    step_name: str | None = Field(
        default=None,
        description="Workflow step or service step name when applicable.",
    )
    field_paths: list[str] = Field(
        default_factory=list,
        description="Field paths directly affected by the issue when known.",
    )
    severity: QualitySeverity = Field(description="Severity of the issue.")
    blocking: bool = Field(description="Whether the issue should block downstream progression.")
    message: str = Field(description="Human-readable explanation of the issue.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Related artifact identifiers that help explain the issue.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the issue record.")

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        """Require explicit issue identifiers and messaging."""

        if not self.check_name:
            raise ValueError("check_name must be non-empty.")
        if not self.check_code:
            raise ValueError("check_code must be non-empty.")
        if not self.target_type:
            raise ValueError("target_type must be non-empty.")
        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class ContractViolation(TimestampedModel):
    """One explicit contract breach recorded by the quality layer."""

    contract_violation_id: str = Field(description="Canonical contract-violation identifier.")
    contract_name: str = Field(description="Stable name of the violated contract.")
    target_type: str = Field(description="Artifact or input type affected by the violation.")
    target_id: str = Field(description="Artifact or input identifier affected by the violation.")
    workflow_name: str | None = Field(
        default=None,
        description="Workflow name when the violation is tied to one workflow boundary.",
    )
    step_name: str | None = Field(
        default=None,
        description="Workflow step or service step name when applicable.",
    )
    offending_field_paths: list[str] = Field(
        default_factory=list,
        description="Field paths directly violating the contract when known.",
    )
    severity: QualitySeverity = Field(description="Severity of the violation.")
    blocking: bool = Field(description="Whether the violation blocks downstream progression.")
    refusal_reason: RefusalReason = Field(description="Refusal reason attached to the breach.")
    message: str = Field(description="Human-readable explanation of the contract breach.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Related artifact identifiers tied to the breach.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the contract violation.")

    @model_validator(mode="after")
    def validate_violation(self) -> Self:
        """Require explicit contract, target, and message semantics."""

        if not self.contract_name:
            raise ValueError("contract_name must be non-empty.")
        if not self.target_type:
            raise ValueError("target_type must be non-empty.")
        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class DataQualityCheck(TimestampedModel):
    """One executed quality check attached to a validation gate."""

    data_quality_check_id: str = Field(description="Canonical data-quality check identifier.")
    validation_gate_id: str = Field(description="Owning validation-gate identifier.")
    target_type: str = Field(description="Artifact or input type assessed by the check.")
    target_id: str = Field(description="Artifact or input identifier assessed by the check.")
    check_name: str = Field(description="Human-readable name of the check.")
    check_code: str = Field(description="Stable code of the check.")
    decision: QualityDecision = Field(description="Decision emitted by the check.")
    severity: QualitySeverity = Field(description="Highest severity observed for the check.")
    data_quality_issue_ids: list[str] = Field(
        default_factory=list,
        description="Issue identifiers recorded by the check.",
    )
    contract_violation_ids: list[str] = Field(
        default_factory=list,
        description="Contract-violation identifiers recorded by the check.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes or interpretation details for the check.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the check.")

    @model_validator(mode="after")
    def validate_check(self) -> Self:
        """Require explicit check linkage and semantics."""

        if not self.validation_gate_id:
            raise ValueError("validation_gate_id must be non-empty.")
        if not self.target_type:
            raise ValueError("target_type must be non-empty.")
        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not self.check_name:
            raise ValueError("check_name must be non-empty.")
        if not self.check_code:
            raise ValueError("check_code must be non-empty.")
        return self


class InputCompletenessReport(TimestampedModel):
    """Structured completeness report for inputs admitted into a workflow boundary."""

    input_completeness_report_id: str = Field(
        description="Canonical input-completeness report identifier."
    )
    target_type: str = Field(description="Artifact or input type covered by the report.")
    target_id: str = Field(description="Artifact or input identifier covered by the report.")
    required_fields: list[str] = Field(
        default_factory=list,
        description="Required field names or semantic requirements for the target.",
    )
    present_fields: list[str] = Field(
        default_factory=list,
        description="Required fields that were present or satisfied.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Required fields that were missing or unsatisfied.",
    )
    completeness_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of required fields that were satisfied.",
    )
    decision: QualityDecision = Field(description="Decision implied by the completeness result.")
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes about missing or satisfied fields.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the completeness report.")

    @model_validator(mode="after")
    def validate_completeness(self) -> Self:
        """Require a coherent completeness report."""

        required = set(self.required_fields)
        present = set(self.present_fields)
        missing = set(self.missing_fields)
        if not self.target_type:
            raise ValueError("target_type must be non-empty.")
        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not present.issubset(required):
            raise ValueError("present_fields must be a subset of required_fields.")
        if not missing.issubset(required):
            raise ValueError("missing_fields must be a subset of required_fields.")
        if present & missing:
            raise ValueError("present_fields and missing_fields must be disjoint.")
        if required and round(self.completeness_ratio, 6) != round(len(present) / len(required), 6):
            raise ValueError("completeness_ratio must match the required/present field counts.")
        return self


class ValidationGate(TimestampedModel):
    """Top-level gate artifact describing one downstream admission decision."""

    validation_gate_id: str = Field(description="Canonical validation-gate identifier.")
    gate_name: str = Field(description="Stable gate name, for example `signal_generation_output`.")
    workflow_name: str = Field(description="Workflow name associated with the gate.")
    step_name: str = Field(description="Workflow step or service boundary associated with the gate.")
    target_type: str = Field(description="Artifact or input type covered by the gate.")
    target_id: str = Field(description="Artifact or input identifier covered by the gate.")
    decision: QualityDecision = Field(description="Overall gate decision.")
    refusal_reason: RefusalReason | None = Field(
        default=None,
        description="Primary refusal or quarantine reason when the gate blocks progression.",
    )
    quarantined: bool = Field(
        default=False,
        description="Whether the gate explicitly quarantined the target from normal persistence or downstream use.",
    )
    data_quality_check_ids: list[str] = Field(
        default_factory=list,
        description="Child data-quality check identifiers attached to the gate.",
    )
    data_quality_issue_ids: list[str] = Field(
        default_factory=list,
        description="Child issue identifiers attached to the gate.",
    )
    contract_violation_ids: list[str] = Field(
        default_factory=list,
        description="Child contract-violation identifiers attached to the gate.",
    )
    input_completeness_report_id: str | None = Field(
        default=None,
        description="Input-completeness report identifier when one was recorded.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes explaining the gate outcome.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the gate.")

    @model_validator(mode="after")
    def validate_gate(self) -> Self:
        """Require coherent refusal and quarantine semantics."""

        if not self.gate_name:
            raise ValueError("gate_name must be non-empty.")
        if not self.workflow_name:
            raise ValueError("workflow_name must be non-empty.")
        if not self.step_name:
            raise ValueError("step_name must be non-empty.")
        if not self.target_type:
            raise ValueError("target_type must be non-empty.")
        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if self.decision in {QualityDecision.REFUSE, QualityDecision.QUARANTINE}:
            if self.refusal_reason is None:
                raise ValueError("refusal_reason is required for refuse and quarantine decisions.")
        if self.decision is QualityDecision.QUARANTINE and not self.quarantined:
            raise ValueError("quarantined must be true when decision is `quarantine`.")
        if self.quarantined and self.decision is not QualityDecision.QUARANTINE:
            raise ValueError("quarantined may only be true when decision is `quarantine`.")
        return self
