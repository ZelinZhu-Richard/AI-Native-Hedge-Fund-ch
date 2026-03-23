from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from libraries.schemas.base import (
    ProvenanceRecord,
    RiskCheckStatus,
    StrictModel,
    TimestampedModel,
)


class SelectionRule(TimestampedModel):
    """Code-owned deterministic rule definition used by portfolio construction."""

    selection_rule_id: str = Field(description="Canonical selection-rule identifier.")
    rule_name: str = Field(description="Stable rule name.")
    rule_stage: str = Field(description="Workflow stage where the rule is applied.")
    description: str = Field(description="Human-readable description of the rule.")
    active: bool = Field(default=True, description="Whether the rule is enforced.")
    notes: list[str] = Field(
        default_factory=list,
        description="Additional explicit notes describing the current rule behavior.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the rule definition.")

    @model_validator(mode="after")
    def validate_rule(self) -> SelectionRule:
        """Require visible rule naming and description."""

        if not self.rule_name:
            raise ValueError("rule_name must be non-empty.")
        if not self.rule_stage:
            raise ValueError("rule_stage must be non-empty.")
        if not self.description:
            raise ValueError("description must be non-empty.")
        return self


class ConstraintSet(TimestampedModel):
    """Applied construction rule and constraint set for one proposal run."""

    constraint_set_id: str = Field(description="Canonical constraint-set identifier.")
    portfolio_proposal_id: str = Field(description="Portfolio proposal evaluated by the set.")
    portfolio_constraint_ids: list[str] = Field(
        default_factory=list,
        description="Portfolio-constraint identifiers applied during construction.",
    )
    selection_rule_ids: list[str] = Field(
        default_factory=list,
        description="Selection-rule identifiers applied during construction.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions that shaped this construction pass.",
    )
    summary: str = Field(description="Operator-readable summary of the applied constraint set.")
    provenance: ProvenanceRecord = Field(description="Traceability for the constraint set.")

    @model_validator(mode="after")
    def validate_constraint_set(self) -> ConstraintSet:
        """Require explicit linkage and summary text."""

        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.selection_rule_ids:
            raise ValueError("selection_rule_ids must contain at least one rule.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ConstraintResult(TimestampedModel):
    """One explicit constraint application result for a candidate or proposal."""

    constraint_result_id: str = Field(description="Canonical constraint-result identifier.")
    constraint_set_id: str = Field(description="Constraint-set identifier for the result.")
    subject_type: str = Field(
        description="Subject checked, such as `candidate_signal`, `position_idea`, or `portfolio_proposal`."
    )
    subject_id: str = Field(description="Identifier of the checked subject.")
    portfolio_constraint_id: str = Field(description="Portfolio-constraint identifier applied.")
    status: RiskCheckStatus = Field(description="Constraint outcome status.")
    binding: bool = Field(description="Whether the constraint actively bound or blocked selection.")
    observed_value: float | None = Field(
        default=None,
        description="Observed metric value when numeric.",
    )
    limit_value: float | None = Field(
        default=None,
        description="Configured hard limit when numeric.",
    )
    headroom_value: float | None = Field(
        default=None,
        description="Remaining headroom after the check when numeric.",
    )
    unit: str | None = Field(default=None, description="Unit for numeric values.")
    message: str = Field(description="Human-readable explanation of the result.")
    provenance: ProvenanceRecord = Field(description="Traceability for the result.")

    @model_validator(mode="after")
    def validate_constraint_result(self) -> ConstraintResult:
        """Require explicit linkage and coherent numeric semantics."""

        if not self.constraint_set_id:
            raise ValueError("constraint_set_id must be non-empty.")
        if not self.subject_type:
            raise ValueError("subject_type must be non-empty.")
        if not self.subject_id:
            raise ValueError("subject_id must be non-empty.")
        if not self.portfolio_constraint_id:
            raise ValueError("portfolio_constraint_id must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        numeric_values = [self.observed_value, self.limit_value, self.headroom_value]
        if any(value is not None for value in numeric_values) and not self.unit:
            raise ValueError("unit is required when numeric values are supplied.")
        return self


class PositionSizingRationale(TimestampedModel):
    """Explicit explanation of how one included position ended at its final weight."""

    position_sizing_rationale_id: str = Field(
        description="Canonical position-sizing rationale identifier."
    )
    position_idea_id: str = Field(description="Included position idea identifier.")
    signal_id: str = Field(description="Signal motivating the included idea.")
    base_weight_bps: int = Field(description="Base weight before explicit caps were applied.")
    final_weight_bps: int = Field(description="Final selected weight in basis points.")
    max_weight_bps: int = Field(description="Hard maximum weight for the position.")
    sizing_rule_name: str = Field(description="Stable sizing rule name.")
    binding_constraint_ids: list[str] = Field(
        default_factory=list,
        description="Constraint identifiers that actively bound the final weight.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions that shaped the selected size.",
    )
    summary: str = Field(description="Operator-readable summary of the sizing rationale.")
    provenance: ProvenanceRecord = Field(description="Traceability for the rationale.")

    @model_validator(mode="after")
    def validate_rationale(self) -> PositionSizingRationale:
        """Require coherent sizing semantics."""

        if not self.position_idea_id:
            raise ValueError("position_idea_id must be non-empty.")
        if not self.signal_id:
            raise ValueError("signal_id must be non-empty.")
        if not self.sizing_rule_name:
            raise ValueError("sizing_rule_name must be non-empty.")
        if self.base_weight_bps <= 0:
            raise ValueError("base_weight_bps must be greater than zero.")
        if self.final_weight_bps <= 0:
            raise ValueError("final_weight_bps must be greater than zero.")
        if self.max_weight_bps <= 0:
            raise ValueError("max_weight_bps must be greater than zero.")
        if self.final_weight_bps > self.max_weight_bps:
            raise ValueError("final_weight_bps must not exceed max_weight_bps.")
        if self.base_weight_bps < self.final_weight_bps:
            raise ValueError("base_weight_bps must be greater than or equal to final_weight_bps.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ProposalRejectionReason(StrictModel):
    """Structured reason that one candidate signal was rejected during construction."""

    reason_code: str = Field(description="Stable rejection reason code.")
    message: str = Field(description="Human-readable explanation of the rejection.")
    blocking: bool = Field(description="Whether the rejection reflects a blocking condition.")
    related_constraint_ids: list[str] = Field(
        default_factory=list,
        description="Constraint identifiers directly relevant to the rejection.",
    )
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifact identifiers directly relevant to the rejection.",
    )

    @model_validator(mode="after")
    def validate_reason(self) -> ProposalRejectionReason:
        """Require visible rejection semantics."""

        if not self.reason_code:
            raise ValueError("reason_code must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class ConstructionDecision(TimestampedModel):
    """Explicit include or reject decision for one candidate signal."""

    construction_decision_id: str = Field(description="Canonical construction-decision identifier.")
    portfolio_selection_summary_id: str = Field(
        description="Owning portfolio-selection summary identifier."
    )
    company_id: str = Field(description="Covered company identifier.")
    signal_id: str = Field(description="Candidate signal identifier.")
    decision_outcome: Literal["included", "rejected"] = Field(
        description="Whether the candidate survived portfolio construction."
    )
    position_idea_id: str | None = Field(
        default=None,
        description="Included position idea identifier when the candidate survived selection.",
    )
    position_sizing_rationale_id: str | None = Field(
        default=None,
        description="Position-sizing rationale identifier when the candidate survived selection.",
    )
    selection_rule_ids: list[str] = Field(
        default_factory=list,
        description="Selection rules directly involved in the decision.",
    )
    constraint_result_ids: list[str] = Field(
        default_factory=list,
        description="Constraint-result identifiers directly involved in the decision.",
    )
    proposal_rejection_reasons: list[ProposalRejectionReason] = Field(
        default_factory=list,
        description="Explicit rejection reasons when the candidate was not selected.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions carried into the decision.",
    )
    summary: str = Field(description="Operator-readable summary of the decision.")
    provenance: ProvenanceRecord = Field(description="Traceability for the decision.")

    @model_validator(mode="after")
    def validate_decision(self) -> ConstructionDecision:
        """Require included and rejected decisions to remain explicit."""

        if not self.portfolio_selection_summary_id:
            raise ValueError("portfolio_selection_summary_id must be non-empty.")
        if not self.company_id:
            raise ValueError("company_id must be non-empty.")
        if not self.signal_id:
            raise ValueError("signal_id must be non-empty.")
        if not self.selection_rule_ids:
            raise ValueError("selection_rule_ids must contain at least one rule.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if self.decision_outcome == "included":
            if self.position_idea_id is None:
                raise ValueError("position_idea_id is required when decision_outcome is included.")
            if self.position_sizing_rationale_id is None:
                raise ValueError(
                    "position_sizing_rationale_id is required when decision_outcome is included."
                )
            if self.proposal_rejection_reasons:
                raise ValueError(
                    "proposal_rejection_reasons must be empty when decision_outcome is included."
                )
        else:
            if not self.proposal_rejection_reasons:
                raise ValueError(
                    "proposal_rejection_reasons must contain at least one reason when rejected."
                )
        return self


class SelectionConflict(TimestampedModel):
    """Explicit conflict record for competing construction candidates."""

    selection_conflict_id: str = Field(description="Canonical selection-conflict identifier.")
    portfolio_selection_summary_id: str = Field(
        description="Owning portfolio-selection summary identifier."
    )
    company_id: str = Field(description="Covered company identifier.")
    conflict_kind: str = Field(description="Stable conflict kind.")
    candidate_signal_ids: list[str] = Field(
        default_factory=list,
        description="Candidate signals participating in the conflict.",
    )
    resolved_in_favor_of_signal_id: str | None = Field(
        default=None,
        description="Winning signal identifier when the conflict was resolved.",
    )
    summary: str = Field(description="Operator-readable summary of the conflict.")
    provenance: ProvenanceRecord = Field(description="Traceability for the conflict.")

    @model_validator(mode="after")
    def validate_conflict(self) -> SelectionConflict:
        """Require explicit conflict participants and explanation."""

        if not self.portfolio_selection_summary_id:
            raise ValueError("portfolio_selection_summary_id must be non-empty.")
        if not self.company_id:
            raise ValueError("company_id must be non-empty.")
        if not self.conflict_kind:
            raise ValueError("conflict_kind must be non-empty.")
        if len(self.candidate_signal_ids) < 2:
            raise ValueError("candidate_signal_ids must contain at least two signals.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class PortfolioSelectionSummary(TimestampedModel):
    """Parent construction artifact describing one proposal's selection outcomes."""

    portfolio_selection_summary_id: str = Field(
        description="Canonical portfolio-selection summary identifier."
    )
    portfolio_proposal_id: str = Field(description="Portfolio proposal identifier.")
    company_id: str = Field(description="Covered company identifier.")
    constraint_set_id: str = Field(description="Applied constraint-set identifier.")
    selection_rule_ids: list[str] = Field(
        default_factory=list,
        description="Selection-rule identifiers active during construction.",
    )
    construction_decision_ids: list[str] = Field(
        default_factory=list,
        description="Construction-decision identifiers recorded for candidate signals.",
    )
    selection_conflict_ids: list[str] = Field(
        default_factory=list,
        description="Selection-conflict identifiers recorded during candidate competition.",
    )
    candidate_signal_ids: list[str] = Field(
        default_factory=list,
        description="Candidate signal identifiers considered by the proposal engine.",
    )
    included_signal_ids: list[str] = Field(
        default_factory=list,
        description="Signal identifiers that survived selection.",
    )
    included_position_idea_ids: list[str] = Field(
        default_factory=list,
        description="Position-idea identifiers included in the proposal.",
    )
    rejected_signal_ids: list[str] = Field(
        default_factory=list,
        description="Signal identifiers explicitly rejected during construction.",
    )
    binding_constraint_ids: list[str] = Field(
        default_factory=list,
        description="Constraint identifiers that actively bound or blocked selection.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions that shaped the selection summary.",
    )
    summary: str = Field(description="Operator-readable summary of proposal construction.")
    provenance: ProvenanceRecord = Field(description="Traceability for the summary.")

    @model_validator(mode="after")
    def validate_summary(self) -> PortfolioSelectionSummary:
        """Require explicit proposal linkage and explanation."""

        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.company_id:
            raise ValueError("company_id must be non-empty.")
        if not self.constraint_set_id:
            raise ValueError("constraint_set_id must be non-empty.")
        if not self.selection_rule_ids:
            raise ValueError("selection_rule_ids must contain at least one rule.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self
