from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from libraries.schemas.base import (
    ConfidenceAssessment,
    ConstraintType,
    PaperTradeStatus,
    PortfolioProposalStatus,
    PositionIdeaStatus,
    PositionSide,
    ProvenanceRecord,
    ReviewOutcome,
    RiskCheckStatus,
    Severity,
    TimestampedModel,
)


class PositionIdea(TimestampedModel):
    """A candidate expression of a signal in portfolio terms."""

    position_idea_id: str = Field(description="Canonical position idea identifier.")
    company_id: str = Field(description="Covered company identifier.")
    signal_id: str = Field(description="Signal that motivated the idea.")
    symbol: str = Field(description="Tradable symbol for simulated expression.")
    instrument_type: str = Field(description="Instrument type, for example `equity` or `adr`.")
    side: PositionSide = Field(description="Directional expression of the idea.")
    thesis_summary: str = Field(description="Concise reason the idea exists.")
    entry_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions required before entering the paper position.",
    )
    exit_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that should close or reduce the paper position.",
    )
    target_horizon: str = Field(description="Expected holding horizon.")
    proposed_weight_bps: int = Field(description="Target portfolio weight in basis points.")
    max_weight_bps: int = Field(description="Hard cap for the position in basis points.")
    evidence_span_ids: list[str] = Field(
        default_factory=list,
        description="Evidence spans supporting the idea.",
    )
    status: PositionIdeaStatus = Field(description="Position idea lifecycle status.")
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the idea.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the position idea.")

    @model_validator(mode="after")
    def validate_weight_limits(self) -> PositionIdea:
        """Ensure proposed weights are consistent with side and hard caps."""

        if abs(self.proposed_weight_bps) > self.max_weight_bps:
            raise ValueError(
                "proposed_weight_bps must not exceed max_weight_bps in absolute value."
            )
        if self.side == PositionSide.FLAT and self.proposed_weight_bps != 0:
            raise ValueError("Flat position ideas must have zero proposed weight.")
        return self


class PortfolioConstraint(TimestampedModel):
    """Explicit portfolio construction guardrail."""

    portfolio_constraint_id: str = Field(description="Canonical portfolio constraint identifier.")
    constraint_type: ConstraintType = Field(description="Constraint category.")
    scope: str = Field(description="Scope of the constraint, such as portfolio or sector.")
    hard_limit: float | None = Field(
        default=None, description="Hard maximum or minimum allowed value."
    )
    soft_limit: float | None = Field(default=None, description="Soft warning threshold.")
    unit: str = Field(description="Unit for the limit, for example `bps` or `pct_adv`.")
    description: str = Field(description="Human-readable explanation of the constraint.")
    active: bool = Field(default=True, description="Whether the constraint is currently enforced.")
    provenance: ProvenanceRecord = Field(description="Traceability for the constraint definition.")


class RiskCheck(TimestampedModel):
    """Result of a specific risk or compliance check."""

    risk_check_id: str = Field(description="Canonical risk check identifier.")
    subject_type: str = Field(
        description="Entity type checked, such as `position_idea` or `portfolio_proposal`."
    )
    subject_id: str = Field(description="Identifier of the entity checked.")
    rule_name: str = Field(description="Stable rule name.")
    status: RiskCheckStatus = Field(description="Risk check outcome.")
    severity: Severity = Field(description="Severity of the check outcome.")
    observed_value: float | None = Field(
        default=None, description="Observed metric value when numeric."
    )
    limit_value: float | None = Field(
        default=None, description="Configured threshold when numeric."
    )
    unit: str | None = Field(default=None, description="Unit for observed and limit values.")
    message: str = Field(description="Human-readable explanation of the result.")
    checked_at: datetime = Field(description="UTC timestamp when the rule was evaluated.")
    reviewer_notes: list[str] = Field(
        default_factory=list, description="Optional notes from risk review."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the risk check.")


class PortfolioProposal(TimestampedModel):
    """Candidate paper portfolio assembled from reviewed position ideas."""

    portfolio_proposal_id: str = Field(description="Canonical portfolio proposal identifier.")
    name: str = Field(description="Human-readable proposal name.")
    as_of_time: datetime = Field(description="UTC time at which the proposal is valid.")
    generated_at: datetime = Field(description="UTC timestamp when the proposal was generated.")
    position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Position ideas included in the proposal.",
    )
    constraints: list[PortfolioConstraint] = Field(
        default_factory=list,
        description="Constraints applied during construction.",
    )
    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Risk checks attached to the proposal.",
    )
    gross_exposure_bps: int = Field(description="Gross exposure of the proposal in basis points.")
    net_exposure_bps: int = Field(description="Net exposure of the proposal in basis points.")
    cash_buffer_bps: int = Field(description="Remaining cash buffer in basis points.")
    review_required: bool = Field(
        default=True,
        description="Whether the proposal requires explicit human approval.",
    )
    status: PortfolioProposalStatus = Field(description="Portfolio proposal lifecycle status.")
    summary: str = Field(description="Short summary of the proposal.")
    provenance: ProvenanceRecord = Field(description="Traceability for the proposal.")

    @model_validator(mode="after")
    def validate_exposures(self) -> PortfolioProposal:
        """Ensure proposal exposure fields are internally consistent."""

        if self.gross_exposure_bps < abs(self.net_exposure_bps):
            raise ValueError("gross_exposure_bps must be at least the absolute net exposure.")
        if self.cash_buffer_bps < 0:
            raise ValueError("cash_buffer_bps must be greater than or equal to zero.")
        return self


class ReviewDecision(TimestampedModel):
    """Human review decision attached to a proposal, idea, or trade."""

    review_decision_id: str = Field(description="Canonical review decision identifier.")
    target_type: str = Field(description="Type of entity being reviewed.")
    target_id: str = Field(description="Identifier of the entity being reviewed.")
    reviewer_id: str = Field(description="Human reviewer identifier.")
    outcome: ReviewOutcome = Field(description="Decision outcome.")
    decided_at: datetime = Field(description="UTC timestamp when the decision was made.")
    rationale: str = Field(description="Reason for the decision.")
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Issues preventing approval if the outcome is not approval.",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions attached to the decision.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the review decision.")


class PaperTrade(TimestampedModel):
    """Human-approved simulated trade proposal or simulated fill."""

    paper_trade_id: str = Field(description="Canonical paper trade identifier.")
    portfolio_proposal_id: str = Field(description="Owning portfolio proposal identifier.")
    position_idea_id: str = Field(description="Underlying position idea identifier.")
    symbol: str = Field(description="Tradable symbol for simulation.")
    side: PositionSide = Field(description="Trade direction.")
    quantity: float = Field(description="Simulated quantity to trade.")
    notional_usd: float = Field(description="Simulated notional value in USD.")
    time_in_force: str = Field(description="Requested time-in-force semantics.")
    status: PaperTradeStatus = Field(description="Paper trade lifecycle status.")
    submitted_at: datetime = Field(description="UTC timestamp when the trade was proposed.")
    approved_at: datetime | None = Field(
        default=None, description="UTC timestamp when the trade was approved."
    )
    simulated_fill_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when a simulated fill was recorded.",
    )
    requested_by: str = Field(description="Requester identifier.")
    approved_by: str | None = Field(default=None, description="Approver identifier when approved.")
    execution_notes: list[str] = Field(
        default_factory=list, description="Simulation or review notes."
    )
    slippage_bps_estimate: float | None = Field(
        default=None,
        description="Estimated slippage in basis points for the simulated fill.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the paper trade.")

    @model_validator(mode="after")
    def validate_trade_timestamps(self) -> PaperTrade:
        """Ensure approval and simulated fill times are temporally valid."""

        if self.approved_at is not None and self.approved_at < self.submitted_at:
            raise ValueError("approved_at must be greater than or equal to submitted_at.")
        if self.simulated_fill_at is not None and self.simulated_fill_at < self.submitted_at:
            raise ValueError("simulated_fill_at must be greater than or equal to submitted_at.")
        return self
