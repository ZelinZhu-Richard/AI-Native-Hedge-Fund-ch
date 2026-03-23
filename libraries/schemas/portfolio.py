from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from libraries.schemas.base import (
    ConfidenceAssessment,
    ConstraintType,
    PaperTradeStatus,
    PortfolioProposalStatus,
    PositionIdeaStatus,
    PositionSide,
    ProvenanceRecord,
    RiskCheckStatus,
    Severity,
    TimestampedModel,
)


class PositionIdea(TimestampedModel):
    """A reviewable position expression derived from one signal and linked evidence."""

    position_idea_id: str = Field(description="Canonical position idea identifier.")
    company_id: str = Field(description="Covered company identifier.")
    signal_id: str = Field(description="Signal that motivated the idea.")
    symbol: str = Field(description="Tradable symbol for simulated expression.")
    instrument_type: str = Field(description="Instrument type, for example `equity` or `adr`.")
    side: PositionSide = Field(description="Directional expression of the idea.")
    thesis_summary: str = Field(description="Concise thesis summary for the idea.")
    selection_reason: str = Field(
        description="Short explanation of why the position was selected from the signal set."
    )
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
        description="Exact evidence spans supporting the idea.",
    )
    supporting_evidence_link_ids: list[str] = Field(
        default_factory=list,
        description="Supporting evidence-link identifiers grounding the idea.",
    )
    research_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Upstream research artifact identifiers informing the idea.",
    )
    review_decision_ids: list[str] = Field(
        default_factory=list,
        description="Review-decision identifiers attached to the idea.",
    )
    signal_bundle_id: str | None = Field(
        default=None,
        description="Signal-bundle identifier used to select the motivating signal when applicable.",
    )
    arbitration_decision_id: str | None = Field(
        default=None,
        description="Signal-arbitration decision identifier used for the idea when applicable.",
    )
    construction_decision_id: str | None = Field(
        default=None,
        description="Construction-decision identifier that recorded why this idea survived selection.",
    )
    position_sizing_rationale_id: str | None = Field(
        default=None,
        description="Position-sizing rationale identifier explaining the final selected weight.",
    )
    status: PositionIdeaStatus = Field(description="Position idea lifecycle status.")
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the idea.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the position idea.")

    @model_validator(mode="after")
    def validate_weight_limits(self) -> PositionIdea:
        """Ensure position ideas retain direction, support, and sane sizing."""

        if not self.signal_id:
            raise ValueError("signal_id must be non-empty.")
        if not self.selection_reason:
            raise ValueError("selection_reason must be non-empty.")
        if not self.evidence_span_ids:
            raise ValueError("evidence_span_ids must contain at least one evidence span.")
        if not self.supporting_evidence_link_ids:
            raise ValueError(
                "supporting_evidence_link_ids must contain at least one evidence link."
            )
        if not self.research_artifact_ids:
            raise ValueError("research_artifact_ids must contain at least one artifact identifier.")
        if self.max_weight_bps <= 0:
            raise ValueError("max_weight_bps must be greater than zero.")
        if abs(self.proposed_weight_bps) > self.max_weight_bps:
            raise ValueError(
                "proposed_weight_bps must not exceed max_weight_bps in absolute value."
            )
        if self.side == PositionSide.FLAT:
            if self.proposed_weight_bps != 0:
                raise ValueError("Flat position ideas must have zero proposed weight.")
        elif self.proposed_weight_bps <= 0:
            raise ValueError("Non-flat position ideas must have a positive proposed_weight_bps.")
        return self


class PortfolioConstraint(TimestampedModel):
    """Explicit portfolio construction guardrail."""

    portfolio_constraint_id: str = Field(description="Canonical portfolio constraint identifier.")
    constraint_type: ConstraintType = Field(description="Constraint category.")
    scope: str = Field(description="Scope of the constraint, such as portfolio or single_name.")
    hard_limit: float | None = Field(
        default=None, description="Hard maximum or minimum allowed value."
    )
    soft_limit: float | None = Field(default=None, description="Soft warning threshold.")
    unit: str = Field(description="Unit for the limit, for example `bps` or `pct_adv`.")
    description: str = Field(description="Human-readable explanation of the constraint.")
    active: bool = Field(default=True, description="Whether the constraint is currently enforced.")
    provenance: ProvenanceRecord = Field(description="Traceability for the constraint definition.")


class PortfolioExposureSummary(TimestampedModel):
    """Inspectable exposure summary attached to a portfolio proposal."""

    portfolio_exposure_summary_id: str = Field(
        description="Canonical portfolio-exposure summary identifier."
    )
    gross_exposure_bps: int = Field(description="Gross exposure in basis points.")
    net_exposure_bps: int = Field(description="Net exposure in basis points.")
    long_exposure_bps: int = Field(ge=0, description="Total long exposure in basis points.")
    short_exposure_bps: int = Field(ge=0, description="Total short exposure in basis points.")
    cash_buffer_bps: int = Field(ge=0, description="Remaining cash buffer in basis points.")
    position_count: int = Field(ge=0, description="Number of included positions.")
    turnover_bps_assumption: int = Field(
        ge=0,
        description="Turnover assumption in basis points under the current flat-start rule.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the exposure summary.")

    @model_validator(mode="after")
    def validate_exposures(self) -> PortfolioExposureSummary:
        """Ensure exposure summary fields remain internally consistent."""

        if self.gross_exposure_bps != self.long_exposure_bps + self.short_exposure_bps:
            raise ValueError("gross_exposure_bps must equal long_exposure_bps + short_exposure_bps.")
        if self.net_exposure_bps != self.long_exposure_bps - self.short_exposure_bps:
            raise ValueError("net_exposure_bps must equal long_exposure_bps - short_exposure_bps.")
        if self.gross_exposure_bps < abs(self.net_exposure_bps):
            raise ValueError("gross_exposure_bps must be at least the absolute net exposure.")
        return self


class RiskCheck(TimestampedModel):
    """Explicit result of one risk or compliance rule."""

    risk_check_id: str = Field(description="Canonical risk check identifier.")
    subject_type: str = Field(
        description="Entity type checked, such as `position_idea` or `portfolio_proposal`."
    )
    subject_id: str = Field(description="Identifier of the entity checked.")
    portfolio_constraint_id: str | None = Field(
        default=None,
        description="Constraint identifier when the check is tied to a named constraint.",
    )
    rule_name: str = Field(description="Stable rule name.")
    status: RiskCheckStatus = Field(description="Risk check outcome.")
    severity: Severity = Field(description="Severity of the check outcome.")
    blocking: bool = Field(description="Whether the check should block downstream progression.")
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
        default_factory=list,
        description="Optional notes from risk review.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the risk check.")

    @model_validator(mode="after")
    def validate_check(self) -> RiskCheck:
        """Ensure blocking and numeric limit semantics stay explicit."""

        if self.blocking and self.status == RiskCheckStatus.PASS:
            raise ValueError("Blocking risk checks cannot have PASS status.")
        if (self.observed_value is None) != (self.limit_value is None):
            raise ValueError("observed_value and limit_value must be provided together.")
        if (self.observed_value is not None or self.limit_value is not None) and self.unit is None:
            raise ValueError("unit is required when numeric observed/limit values are supplied.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class PortfolioProposal(TimestampedModel):
    """Reviewable paper portfolio proposal assembled from signal-backed position ideas."""

    portfolio_proposal_id: str = Field(description="Canonical portfolio proposal identifier.")
    name: str = Field(description="Human-readable proposal name.")
    as_of_time: datetime = Field(description="UTC time at which the proposal is valid.")
    generated_at: datetime = Field(description="UTC timestamp when the proposal was generated.")
    target_nav_usd: float = Field(
        default=1_000_000.0,
        gt=0.0,
        description="Target notional capital base used for paper-trade sizing.",
    )
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
    exposure_summary: PortfolioExposureSummary = Field(
        description="Inspectable exposure summary for the proposal."
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Blocking issues preventing approval or downstream progression.",
    )
    review_decision_ids: list[str] = Field(
        default_factory=list,
        description="Review-decision identifiers attached to the proposal.",
    )
    signal_bundle_id: str | None = Field(
        default=None,
        description="Signal-bundle identifier used to source portfolio inputs when applicable.",
    )
    arbitration_decision_id: str | None = Field(
        default=None,
        description="Signal-arbitration decision identifier used by the proposal when applicable.",
    )
    portfolio_attribution_id: str | None = Field(
        default=None,
        description="Portfolio-attribution artifact identifier when proposal analysis has run.",
    )
    stress_test_run_id: str | None = Field(
        default=None,
        description="Stress-test run identifier when proposal analysis has run.",
    )
    portfolio_selection_summary_id: str | None = Field(
        default=None,
        description="Portfolio-selection summary identifier when construction artifacts have been recorded.",
    )
    strategy_to_paper_mapping_id: str | None = Field(
        default=None,
        description="Strategy-to-paper mapping identifier when backtest reconciliation has run.",
    )
    reconciliation_report_id: str | None = Field(
        default=None,
        description="Backtest-to-paper reconciliation report identifier when available.",
    )
    review_required: bool = Field(
        default=True,
        description="Whether the proposal requires explicit human approval.",
    )
    status: PortfolioProposalStatus = Field(description="Portfolio proposal lifecycle status.")
    summary: str = Field(description="Short summary of the proposal.")
    provenance: ProvenanceRecord = Field(description="Traceability for the proposal.")

    @model_validator(mode="after")
    def validate_proposal(self) -> PortfolioProposal:
        """Ensure proposal exposure and blocking state remain aligned."""

        if self.exposure_summary.position_count != len(self.position_ideas):
            raise ValueError("exposure_summary.position_count must match len(position_ideas).")
        if any(check.blocking for check in self.risk_checks) and not self.blocking_issues:
            raise ValueError("blocking_issues must be populated when blocking risk checks exist.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class PaperTrade(TimestampedModel):
    """Human-reviewable paper trade candidate or simulated paper fill."""

    paper_trade_id: str = Field(description="Canonical paper trade identifier.")
    portfolio_proposal_id: str = Field(description="Owning portfolio proposal identifier.")
    position_idea_id: str = Field(description="Underlying position idea identifier.")
    symbol: str = Field(description="Tradable symbol for simulation.")
    side: PositionSide = Field(description="Trade direction.")
    execution_mode: Literal["paper_only"] = Field(
        default="paper_only",
        description="Execution mode. Day 7 supports paper-only trade candidates.",
    )
    quantity: float | None = Field(
        default=None,
        gt=0.0,
        description="Simulated quantity to trade when a reference price is available.",
    )
    notional_usd: float = Field(gt=0.0, description="Simulated notional value in USD.")
    assumed_reference_price_usd: float | None = Field(
        default=None,
        gt=0.0,
        description="Optional reference price used to derive quantity for the paper trade.",
    )
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
    review_decision_ids: list[str] = Field(
        default_factory=list,
        description="Review-decision identifiers attached to the paper trade.",
    )
    execution_notes: list[str] = Field(
        default_factory=list,
        description="Simulation or review notes.",
    )
    slippage_bps_estimate: float | None = Field(
        default=None,
        ge=0.0,
        description="Estimated slippage in basis points for the simulated fill.",
    )
    execution_timing_rule_id: str | None = Field(
        default=None,
        description="Execution-timing rule identifier describing the paper-trade timing semantics.",
    )
    fill_assumption_id: str | None = Field(
        default=None,
        description="Fill-assumption identifier describing the paper-trade fill basis.",
    )
    cost_model_id: str | None = Field(
        default=None,
        description="Cost-model identifier describing the paper-trade cost estimate.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the paper trade.")

    @model_validator(mode="after")
    def validate_trade_timestamps(self) -> PaperTrade:
        """Ensure paper trades stay explicit, non-live, and temporally coherent."""

        if self.side == PositionSide.FLAT:
            raise ValueError("Paper trades must not use a flat side.")
        if self.quantity is not None and self.assumed_reference_price_usd is None:
            raise ValueError(
                "assumed_reference_price_usd is required when quantity is materialized."
            )
        if self.approved_at is not None and self.approved_at < self.submitted_at:
            raise ValueError("approved_at must be greater than or equal to submitted_at.")
        if self.simulated_fill_at is not None and self.simulated_fill_at < self.submitted_at:
            raise ValueError("simulated_fill_at must be greater than or equal to submitted_at.")
        if self.approved_at is not None and self.approved_by is None:
            raise ValueError("approved_by is required when approved_at is provided.")
        if self.status == PaperTradeStatus.APPROVED and self.approved_at is None:
            raise ValueError("approved_at is required when status is APPROVED.")
        if self.status == PaperTradeStatus.SIMULATED and self.simulated_fill_at is None:
            raise ValueError("simulated_fill_at is required when status is SIMULATED.")
        return self
