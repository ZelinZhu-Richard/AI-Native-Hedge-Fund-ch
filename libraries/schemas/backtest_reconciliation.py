from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, Severity, TimestampedModel


class WorkflowScope(StrEnum):
    """Workflow scopes covered by realism and reconciliation artifacts."""

    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"


class TimingAnchor(StrEnum):
    """Named timing anchors used to describe decision and execution semantics."""

    SIGNAL_DECISION_CLOSE = "signal_decision_close"
    SIGNAL_ELIGIBILITY_TIME = "signal_eligibility_time"
    NEXT_SESSION_OPEN = "next_session_open"
    PROPOSAL_AS_OF_TIME = "proposal_as_of_time"
    TRADE_SUBMITTED_AT = "trade_submitted_at"
    HUMAN_APPROVAL_TIME = "human_approval_time"
    NO_AUTOMATIC_EXECUTION = "no_automatic_execution"


class PriceSourceKind(StrEnum):
    """Explicit price basis used by one workflow scope."""

    SYNTHETIC_NEXT_BAR_OPEN = "synthetic_next_bar_open"
    ASSUMED_REFERENCE_PRICE = "assumed_reference_price"
    NO_PRICE_MATERIALIZED = "no_price_materialized"


class QuantityBasis(StrEnum):
    """Explicit quantity basis used by one workflow scope."""

    UNIT_POSITION = "unit_position"
    NOTIONAL_DIVIDED_BY_REFERENCE_PRICE = "notional_divided_by_reference_price"
    NOT_MATERIALIZED = "not_materialized"


class AssumptionMismatchKind(StrEnum):
    """Structured mismatch kinds between backtest and paper assumptions."""

    EXECUTION_ANCHOR_MISMATCH = "execution_anchor_mismatch"
    LAG_MISMATCH = "lag_mismatch"
    COST_MODEL_MISMATCH = "cost_model_mismatch"
    FILL_PRICE_BASIS_MISMATCH = "fill_price_basis_mismatch"
    QUANTITY_BASIS_MISMATCH = "quantity_basis_mismatch"
    APPROVAL_REQUIREMENT_MISMATCH = "approval_requirement_mismatch"


class AvailabilityMismatchKind(StrEnum):
    """Structured timing mismatches between backtest and paper workflows."""

    PROPOSAL_BEFORE_SIGNAL_EFFECTIVE_AT = "proposal_before_signal_effective_at"
    TRADE_SUBMITTED_BEFORE_SIGNAL_EFFECTIVE_AT = "trade_submitted_before_signal_effective_at"
    APPROVAL_AFTER_BACKTEST_EXECUTION_WINDOW = "approval_after_backtest_execution_window"
    BACKTEST_TIMING_INCONSISTENCY = "backtest_timing_inconsistency"


class RealismWarningKind(StrEnum):
    """Explicit simplifications or realism gaps that remain inspectable."""

    SYNTHETIC_PRICE_FIXTURE = "synthetic_price_fixture"
    NO_PAPER_FILL_SIMULATION = "no_paper_fill_simulation"
    MANUAL_REFERENCE_PRICE = "manual_reference_price"
    MISSING_REFERENCE_PRICE = "missing_reference_price"
    FIXED_BPS_COSTS = "fixed_bps_costs"
    APPROVAL_DELAY_UNMODELED = "approval_delay_unmodeled"
    UNIT_POSITION_SIMPLIFICATION = "unit_position_simplification"
    NO_INTRADAY_MICROSTRUCTURE = "no_intraday_microstructure"
    ESTIMATE_ONLY_PAPER_COST_MODEL = "estimate_only_paper_cost_model"


class ExecutionTimingRule(TimestampedModel):
    """Explicit timing semantics for one workflow scope."""

    execution_timing_rule_id: str = Field(description="Canonical execution-timing-rule identifier.")
    workflow_scope: WorkflowScope = Field(description="Workflow scope described by the rule.")
    rule_name: str = Field(description="Stable rule identifier.")
    decision_anchor: TimingAnchor = Field(description="Primary decision anchor for the workflow.")
    eligibility_anchor: TimingAnchor = Field(
        description="Anchor used to judge when an input becomes eligible."
    )
    execution_anchor: TimingAnchor = Field(description="Anchor used to describe execution timing.")
    requires_human_approval: bool = Field(
        description="Whether explicit human approval is required before execution can occur."
    )
    execution_lag_bars: int | None = Field(
        default=None,
        ge=0,
        description="Bar lag used when the workflow has an explicit delayed execution model.",
    )
    signal_availability_buffer_minutes: int | None = Field(
        default=None,
        ge=0,
        description="Extra timing buffer applied before an input becomes eligible.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Explicit timing caveats and assumptions.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the timing rule.")

    @model_validator(mode="after")
    def validate_rule_name(self) -> Self:
        """Require a stable non-empty rule name."""

        if not self.rule_name:
            raise ValueError("rule_name must be non-empty.")
        return self


class FillAssumption(TimestampedModel):
    """Explicit fill-basis assumption for one workflow scope."""

    fill_assumption_id: str = Field(description="Canonical fill-assumption identifier.")
    workflow_scope: WorkflowScope = Field(description="Workflow scope described by the assumption.")
    price_source_kind: PriceSourceKind = Field(description="Price basis used by the workflow.")
    quantity_basis: QuantityBasis = Field(description="Quantity basis used by the workflow.")
    fill_delay_description: str = Field(description="Human-readable description of fill timing.")
    notes: list[str] = Field(
        default_factory=list,
        description="Explicit fill caveats and limitations.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the fill assumption.")

    @model_validator(mode="after")
    def validate_delay_description(self) -> Self:
        """Require explicit fill-delay semantics."""

        if not self.fill_delay_description:
            raise ValueError("fill_delay_description must be non-empty.")
        return self


class CostModel(TimestampedModel):
    """Explicit cost and slippage assumptions for one workflow scope."""

    cost_model_id: str = Field(description="Canonical cost-model identifier.")
    workflow_scope: WorkflowScope = Field(description="Workflow scope described by the cost model.")
    transaction_cost_bps: float | None = Field(
        default=None,
        ge=0.0,
        description="One-way transaction cost assumption in basis points when known.",
    )
    slippage_bps: float | None = Field(
        default=None,
        ge=0.0,
        description="One-way slippage assumption in basis points when known.",
    )
    estimate_only: bool = Field(
        description="Whether the cost model is explicitly heuristic rather than simulation-grade."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Explicit cost-model caveats and limitations.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the cost model.")


class AssumptionMismatch(TimestampedModel):
    """Structured mismatch between backtest and paper assumptions."""

    assumption_mismatch_id: str = Field(description="Canonical assumption-mismatch identifier.")
    mismatch_kind: AssumptionMismatchKind = Field(description="Structured mismatch classification.")
    backtest_value_repr: str = Field(description="Backtest-side value representation.")
    paper_value_repr: str = Field(description="Paper-side value representation.")
    severity: Severity = Field(description="Severity of the mismatch.")
    blocking: bool = Field(description="Whether the mismatch should mark the pair inconsistent.")
    message: str = Field(description="Human-readable mismatch explanation.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifact identifiers implicated in the mismatch.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the mismatch.")

    @model_validator(mode="after")
    def validate_message(self) -> Self:
        """Require visible mismatch messaging."""

        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class AvailabilityMismatch(TimestampedModel):
    """Structured timing mismatch or missing execution-time anchor."""

    availability_mismatch_id: str = Field(description="Canonical availability-mismatch identifier.")
    mismatch_kind: AvailabilityMismatchKind = Field(description="Structured mismatch classification.")
    required_time: datetime | None = Field(
        default=None,
        description="Required UTC time implied by one side of the comparison when available.",
    )
    observed_time: datetime | None = Field(
        default=None,
        description="Observed UTC time on the compared workflow when available.",
    )
    severity: Severity = Field(description="Severity of the mismatch.")
    blocking: bool = Field(description="Whether the mismatch should mark the pair inconsistent.")
    message: str = Field(description="Human-readable mismatch explanation.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifact identifiers implicated in the mismatch.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the mismatch.")

    @model_validator(mode="after")
    def validate_message(self) -> Self:
        """Require visible mismatch messaging."""

        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class RealismWarning(TimestampedModel):
    """Explicit simplification or realism gap preserved for review."""

    realism_warning_id: str = Field(description="Canonical realism-warning identifier.")
    warning_kind: RealismWarningKind = Field(description="Structured realism-gap classification.")
    severity: Severity = Field(description="Severity of the realism warning.")
    message: str = Field(description="Human-readable realism warning.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifact identifiers implicated in the realism warning.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the realism warning.")

    @model_validator(mode="after")
    def validate_message(self) -> Self:
        """Require visible warning messaging."""

        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class StrategyToPaperMapping(TimestampedModel):
    """Stable mapping from one backtest context to one proposal and optional paper trades."""

    strategy_to_paper_mapping_id: str = Field(
        description="Canonical strategy-to-paper mapping identifier."
    )
    company_id: str = Field(description="Covered company identifier.")
    backtest_run_id: str | None = Field(
        default=None,
        description="Matched backtest run when reconciliation had one available.",
    )
    portfolio_proposal_id: str = Field(description="Mapped portfolio proposal identifier.")
    paper_trade_ids: list[str] = Field(
        default_factory=list,
        description="Mapped paper-trade identifiers when candidates exist.",
    )
    position_idea_ids: list[str] = Field(
        default_factory=list,
        description="Mapped position-idea identifiers used by the proposal.",
    )
    signal_ids: list[str] = Field(
        default_factory=list,
        description="Mapped signal identifiers used by the compared workflows.",
    )
    matched_signal_family: str | None = Field(
        default=None,
        description="Resolved comparable signal family when available.",
    )
    matched_ablation_view: str | None = Field(
        default=None,
        description="Resolved comparable ablation view when available.",
    )
    backtest_execution_timing_rule_id: str | None = Field(
        default=None,
        description="Backtest-side timing rule identifier when available.",
    )
    paper_execution_timing_rule_id: str = Field(
        description="Paper-side timing rule identifier used in the mapping."
    )
    backtest_fill_assumption_id: str | None = Field(
        default=None,
        description="Backtest-side fill assumption identifier when available.",
    )
    paper_fill_assumption_id: str = Field(
        description="Paper-side fill assumption identifier used in the mapping."
    )
    backtest_cost_model_id: str | None = Field(
        default=None,
        description="Backtest-side cost-model identifier when available.",
    )
    paper_cost_model_id: str = Field(
        description="Paper-side cost-model identifier used in the mapping."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes about how the mapping was resolved.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the mapping.")

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        """Require proposal and paper-side linkage."""

        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.paper_execution_timing_rule_id:
            raise ValueError("paper_execution_timing_rule_id must be non-empty.")
        if not self.paper_fill_assumption_id:
            raise ValueError("paper_fill_assumption_id must be non-empty.")
        if not self.paper_cost_model_id:
            raise ValueError("paper_cost_model_id must be non-empty.")
        return self


class ReconciliationReport(TimestampedModel):
    """Parent summary comparing one backtest context to one paper workflow context."""

    reconciliation_report_id: str = Field(description="Canonical reconciliation-report identifier.")
    company_id: str = Field(description="Covered company identifier.")
    strategy_to_paper_mapping_id: str = Field(
        description="Owning strategy-to-paper mapping identifier."
    )
    assumption_mismatch_ids: list[str] = Field(
        default_factory=list,
        description="Assumption mismatch identifiers recorded for the comparison.",
    )
    availability_mismatch_ids: list[str] = Field(
        default_factory=list,
        description="Availability mismatch identifiers recorded for the comparison.",
    )
    realism_warning_ids: list[str] = Field(
        default_factory=list,
        description="Realism warning identifiers recorded for the comparison.",
    )
    highest_severity: Severity = Field(description="Highest severity observed in the report.")
    internally_consistent: bool = Field(
        description="Whether the compared workflows remained internally consistent."
    )
    review_required: bool = Field(
        default=True,
        description="Whether the report should be surfaced to operators for review.",
    )
    summary: str = Field(description="Human-readable reconciliation summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the report.")

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        """Require explicit report text and mapping linkage."""

        if not self.strategy_to_paper_mapping_id:
            raise ValueError("strategy_to_paper_mapping_id must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self
