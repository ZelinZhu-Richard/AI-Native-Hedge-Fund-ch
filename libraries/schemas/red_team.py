from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, Severity, StrictModel, TimestampedModel
from libraries.schemas.research import EvaluationStatus

# Reuse the shared severity scale so red-team, evaluation, risk, and monitoring
# findings stay directly comparable.
FailureSeverity = Severity


class AdversarialInput(TimestampedModel):
    """Structured adversarial input applied to a cloned artifact during red-team checks."""

    adversarial_input_id: str = Field(description="Canonical adversarial-input identifier.")
    input_kind: str = Field(description="Stable adversarial input category.")
    description: str = Field(description="Human-readable description of the adversarial mutation.")
    target_type: str = Field(description="Artifact type targeted by the adversarial input.")
    target_id: str = Field(description="Artifact identifier targeted by the adversarial input.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts referenced by the adversarial input.",
    )
    fixture_path: str | None = Field(
        default=None,
        description="Optional fixture path used to define or reproduce the adversarial input.",
    )
    payload_summary: str | None = Field(
        default=None,
        description="Optional summary of the adversarial payload without dumping full content.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the adversarial input.")

    @model_validator(mode="after")
    def validate_adversarial_input(self) -> AdversarialInput:
        """Require explicit target linkage and a visible mutation description."""

        if not self.input_kind:
            raise ValueError("input_kind must be non-empty.")
        if not self.description:
            raise ValueError("description must be non-empty.")
        if not self.target_type or not self.target_id:
            raise ValueError("target_type and target_id must be non-empty.")
        return self


class RecommendedMitigation(StrictModel):
    """Concrete follow-up action suggested by a red-team guardrail violation."""

    recommended_mitigation_id: str = Field(description="Canonical mitigation identifier.")
    summary: str = Field(description="Short mitigation summary.")
    required_action: str = Field(description="Specific action needed to address the weakness.")
    owner_hint: str | None = Field(
        default=None,
        description="Suggested owner or subsystem for the mitigation.",
    )
    blocking: bool = Field(description="Whether the mitigation should block trust progression.")
    notes: list[str] = Field(
        default_factory=list,
        description="Optional implementation or review notes.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the mitigation guidance.")

    @model_validator(mode="after")
    def validate_mitigation(self) -> RecommendedMitigation:
        """Require concrete mitigation text instead of vague advice."""

        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if not self.required_action:
            raise ValueError("required_action must be non-empty.")
        return self


class GuardrailViolation(TimestampedModel):
    """Explicit guardrail breach found by the red-team layer."""

    guardrail_violation_id: str = Field(description="Canonical guardrail-violation identifier.")
    red_team_case_id: str = Field(description="Owning red-team case identifier.")
    guardrail_name: str = Field(description="Stable guardrail name.")
    target_type: str = Field(description="Artifact type affected by the violation.")
    target_id: str = Field(description="Artifact identifier affected by the violation.")
    severity: FailureSeverity = Field(description="Severity of the violation.")
    blocking: bool = Field(description="Whether the violation should fail the red-team case.")
    message: str = Field(description="Human-readable explanation of the violation.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly related to the violation.",
    )
    recommended_mitigations: list[RecommendedMitigation] = Field(
        default_factory=list,
        description="Concrete mitigations suggested for this violation.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the guardrail violation.")

    @model_validator(mode="after")
    def validate_violation(self) -> GuardrailViolation:
        """Require explicit guardrail naming and messaging."""

        if not self.guardrail_name:
            raise ValueError("guardrail_name must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class SafetyFinding(TimestampedModel):
    """Structured summary of a red-team scenario outcome for one target."""

    safety_finding_id: str = Field(description="Canonical safety-finding identifier.")
    red_team_case_id: str = Field(description="Owning red-team case identifier.")
    target_type: str = Field(description="Artifact type summarized by the finding.")
    target_id: str = Field(description="Artifact identifier summarized by the finding.")
    status: EvaluationStatus = Field(description="Outcome classification for the finding.")
    summary: str = Field(description="Short summary of the exposed weakness or pass condition.")
    guardrail_violation_ids: list[str] = Field(
        default_factory=list,
        description="Guardrail violations contributing to the finding.",
    )
    exposed_weaknesses: list[str] = Field(
        default_factory=list,
        description="Named weaknesses surfaced by the adversarial case.",
    )
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly associated with the finding.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the safety finding.")

    @model_validator(mode="after")
    def validate_finding(self) -> SafetyFinding:
        """Require finding summaries and explicit weakness detail on non-pass cases."""

        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if self.status in {EvaluationStatus.WARN, EvaluationStatus.FAIL} and not any(
            [self.guardrail_violation_ids, self.exposed_weaknesses]
        ):
            raise ValueError(
                "Non-pass safety findings must include guardrail_violation_ids or exposed_weaknesses."
            )
        return self


class RedTeamCase(TimestampedModel):
    """Recorded red-team scenario executed against cloned repository artifacts."""

    red_team_case_id: str = Field(description="Canonical red-team case identifier.")
    name: str = Field(description="Short human-readable case name.")
    scenario_name: str = Field(description="Stable scenario identifier.")
    target_type: str = Field(description="Artifact type targeted by the scenario.")
    target_id: str = Field(description="Artifact identifier targeted by the scenario.")
    adversarial_inputs: list[AdversarialInput] = Field(
        default_factory=list,
        description="Adversarial inputs applied for the scenario.",
    )
    expected_guardrails: list[str] = Field(
        default_factory=list,
        description="Guardrails that should detect the adversarial condition.",
    )
    outcome_status: EvaluationStatus = Field(description="Outcome classification for the case.")
    guardrail_violation_ids: list[str] = Field(
        default_factory=list,
        description="Guardrail-violation identifiers recorded by the case.",
    )
    safety_finding_ids: list[str] = Field(
        default_factory=list,
        description="Safety-finding identifiers recorded by the case.",
    )
    executed_at: datetime = Field(description="UTC timestamp when the case was executed.")
    notes: list[str] = Field(
        default_factory=list,
        description="Important interpretation notes for the case.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the red-team case.")

    @model_validator(mode="after")
    def validate_case(self) -> RedTeamCase:
        """Require visible scenario configuration and structured outputs."""

        if not self.name:
            raise ValueError("name must be non-empty.")
        if not self.scenario_name:
            raise ValueError("scenario_name must be non-empty.")
        if not self.adversarial_inputs:
            raise ValueError("adversarial_inputs must contain at least one input.")
        if not self.expected_guardrails:
            raise ValueError("expected_guardrails must contain at least one guardrail name.")
        if self.outcome_status in {EvaluationStatus.WARN, EvaluationStatus.FAIL} and not any(
            [self.guardrail_violation_ids, self.safety_finding_ids]
        ):
            raise ValueError(
                "Non-pass red-team cases must reference guardrail violations or safety findings."
            )
        return self
