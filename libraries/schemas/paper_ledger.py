from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from libraries.schemas.base import PositionSide, ProvenanceRecord, StrictModel, TimestampedModel


class PaperPositionStateStatus(StrEnum):
    """Lifecycle states for admitted paper positions."""

    APPROVED_PENDING_FILL = "approved_pending_fill"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PositionLifecycleEventType(StrEnum):
    """Explicit lifecycle transitions recorded for paper positions."""

    APPROVAL_ADMITTED = "approval_admitted"
    SIMULATED_FILL_PLACEHOLDER = "simulated_fill_placeholder"
    MARK_UPDATED = "mark_updated"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ReviewFollowupStatus(StrEnum):
    """Lifecycle for post-trade review followups."""

    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ThesisAssessment(StrEnum):
    """Human-authored thesis outcome assessment for one paper position."""

    HELD = "held"
    MIXED = "mixed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class RiskWarningRelevance(StrEnum):
    """Human-authored assessment of whether prior risk warnings mattered."""

    RELEVANT = "relevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    NOT_OBSERVED = "not_observed"
    INCONCLUSIVE = "inconclusive"


class PnLPlaceholder(StrictModel):
    """Explicit placeholder mark-based PnL metadata, not a realized execution record."""

    entry_reference_price_usd: float | None = Field(
        default=None,
        gt=0.0,
        description="Reference entry price used as the placeholder basis when available.",
    )
    current_or_exit_price_usd: float | None = Field(
        default=None,
        gt=0.0,
        description="Current or exit mark used for the placeholder PnL when available.",
    )
    unrealized_pnl_usd: float | None = Field(
        default=None,
        description="Unrealized placeholder PnL when the position remains open.",
    )
    realized_pnl_usd: float | None = Field(
        default=None,
        description="Realized placeholder PnL when the position has been closed.",
    )
    complete: bool = Field(
        description="Whether the placeholder PnL had complete enough inputs to compute honestly."
    )
    calculation_basis: str = Field(
        description="Explicit description of the placeholder calculation basis."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Caveats about coverage, quality, or missing inputs.",
    )

    @model_validator(mode="after")
    def validate_placeholder(self) -> Self:
        """Require explicit calculation semantics and complete placeholder linkage."""

        if not self.calculation_basis:
            raise ValueError("calculation_basis must be non-empty.")
        if self.complete:
            if self.entry_reference_price_usd is None or self.current_or_exit_price_usd is None:
                raise ValueError(
                    "Complete PnLPlaceholder requires both entry_reference_price_usd and current_or_exit_price_usd."
                )
            if self.unrealized_pnl_usd is None and self.realized_pnl_usd is None:
                raise ValueError(
                    "Complete PnLPlaceholder requires unrealized_pnl_usd or realized_pnl_usd."
                )
        return self


class PaperLedgerEntry(TimestampedModel):
    """Append-only ledger entry for one admitted paper position."""

    paper_ledger_entry_id: str = Field(description="Canonical paper-ledger entry identifier.")
    paper_position_state_id: str = Field(description="Paper-position state identifier.")
    paper_trade_id: str = Field(description="Paper-trade identifier linked to the entry.")
    entry_kind: PositionLifecycleEventType = Field(
        description="Lifecycle event kind represented by the ledger entry."
    )
    event_time: datetime = Field(description="UTC timestamp represented by the ledger entry.")
    reference_price_usd: float | None = Field(
        default=None,
        gt=0.0,
        description="Reference price used by the entry when available.",
    )
    quantity_delta: float | None = Field(
        default=None,
        description="Quantity change recorded by the entry when applicable.",
    )
    notional_delta_usd: float | None = Field(
        default=None,
        description="Notional change recorded by the entry when applicable.",
    )
    pnl_placeholder: PnLPlaceholder | None = Field(
        default=None,
        description="Optional placeholder PnL attached to the entry when applicable.",
    )
    related_lifecycle_event_id: str | None = Field(
        default=None,
        description="Lifecycle-event identifier paired with this ledger entry when available.",
    )
    related_review_decision_id: str | None = Field(
        default=None,
        description="Review-decision identifier that triggered the entry when available.",
    )
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Additional related artifact identifiers referenced by the entry.",
    )
    summary: str = Field(description="Operator-readable summary of the entry.")
    provenance: ProvenanceRecord = Field(description="Traceability for the ledger entry.")

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        """Require visible linkage and summary text."""

        if not self.paper_position_state_id:
            raise ValueError("paper_position_state_id must be non-empty.")
        if not self.paper_trade_id:
            raise ValueError("paper_trade_id must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class PaperPositionState(TimestampedModel):
    """Current-state read model for one approved paper trade."""

    paper_position_state_id: str = Field(description="Canonical paper-position state identifier.")
    paper_trade_id: str = Field(description="Linked paper-trade identifier.")
    portfolio_proposal_id: str = Field(description="Parent portfolio-proposal identifier.")
    position_idea_id: str = Field(description="Parent position-idea identifier.")
    signal_id: str = Field(description="Linked signal identifier.")
    company_id: str = Field(description="Covered company identifier.")
    symbol: str = Field(description="Tradable symbol for the admitted paper position.")
    side: PositionSide = Field(description="Directional side of the admitted paper position.")
    state: PaperPositionStateStatus = Field(description="Current lifecycle state.")
    opened_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the paper position first became open.",
    )
    closed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the paper position was closed or cancelled.",
    )
    quantity: float | None = Field(
        default=None,
        gt=0.0,
        description="Current materialized quantity when known.",
    )
    entry_reference_price_usd: float | None = Field(
        default=None,
        gt=0.0,
        description="Reference entry price used for quantity and placeholder PnL when known.",
    )
    latest_reference_price_usd: float | None = Field(
        default=None,
        gt=0.0,
        description="Most recent reference mark carried on the position when known.",
    )
    latest_pnl_placeholder: PnLPlaceholder | None = Field(
        default=None,
        description="Most recent placeholder PnL snapshot for the position when available.",
    )
    latest_lifecycle_event_id: str | None = Field(
        default=None,
        description="Latest lifecycle-event identifier linked to the position.",
    )
    latest_ledger_entry_id: str | None = Field(
        default=None,
        description="Latest ledger-entry identifier linked to the position.",
    )
    review_followup_ids: list[str] = Field(
        default_factory=list,
        description="Open or historical review-followup identifiers linked to the position.",
    )
    trade_outcome_ids: list[str] = Field(
        default_factory=list,
        description="Trade-outcome identifiers linked to the position.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the paper-position state.")

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        """Require coherent time and placeholder materialization semantics."""

        if not self.paper_trade_id:
            raise ValueError("paper_trade_id must be non-empty.")
        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.position_idea_id:
            raise ValueError("position_idea_id must be non-empty.")
        if not self.signal_id:
            raise ValueError("signal_id must be non-empty.")
        if not self.company_id:
            raise ValueError("company_id must be non-empty.")
        if not self.symbol:
            raise ValueError("symbol must be non-empty.")
        if self.quantity is not None and self.entry_reference_price_usd is None:
            raise ValueError(
                "entry_reference_price_usd is required when quantity is materialized."
            )
        if self.closed_at is not None and self.opened_at is not None and self.closed_at < self.opened_at:
            raise ValueError("closed_at must be greater than or equal to opened_at.")
        if self.state in {
            PaperPositionStateStatus.CLOSED,
            PaperPositionStateStatus.CANCELLED,
        } and self.closed_at is None:
            raise ValueError("closed_at is required for closed or cancelled paper positions.")
        return self


class PositionLifecycleEvent(TimestampedModel):
    """Explicit lifecycle transition recorded for one admitted paper position."""

    position_lifecycle_event_id: str = Field(
        description="Canonical position-lifecycle event identifier."
    )
    paper_position_state_id: str = Field(description="Paper-position state identifier.")
    paper_trade_id: str = Field(description="Paper-trade identifier linked to the event.")
    event_type: PositionLifecycleEventType = Field(description="Lifecycle event kind.")
    prior_state: PaperPositionStateStatus | None = Field(
        default=None,
        description="State before the event when a prior state existed.",
    )
    new_state: PaperPositionStateStatus = Field(description="State after the event.")
    happened_at: datetime = Field(description="UTC timestamp when the event happened.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Additional related artifact identifiers referenced by the event.",
    )
    summary: str = Field(description="Operator-readable summary of the event.")
    provenance: ProvenanceRecord = Field(description="Traceability for the lifecycle event.")

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        """Require visible linkage and summary text."""

        if not self.paper_position_state_id:
            raise ValueError("paper_position_state_id must be non-empty.")
        if not self.paper_trade_id:
            raise ValueError("paper_trade_id must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class TradeOutcome(TimestampedModel):
    """Post-trade outcome artifact for a closed or cancelled paper position."""

    trade_outcome_id: str = Field(description="Canonical trade-outcome identifier.")
    paper_position_state_id: str = Field(description="Paper-position state identifier.")
    paper_trade_id: str = Field(description="Linked paper-trade identifier.")
    thesis_assessment: ThesisAssessment = Field(
        description="Human-authored assessment of whether the thesis held up."
    )
    risk_warning_relevance: RiskWarningRelevance = Field(
        description="Human-authored assessment of whether prior risk warnings mattered."
    )
    assumption_notes: list[str] = Field(
        default_factory=list,
        description="Explicit notes about assumptions that shaped the observed outcome.",
    )
    learning_notes: list[str] = Field(
        default_factory=list,
        description="Explicit learning notes that should feed future review and research.",
    )
    pnl_placeholder: PnLPlaceholder | None = Field(
        default=None,
        description="Optional placeholder PnL snapshot recorded with the outcome.",
    )
    summary: str = Field(description="Operator-readable outcome summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the trade outcome.")

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require visible linkage and summary text."""

        if not self.paper_position_state_id:
            raise ValueError("paper_position_state_id must be non-empty.")
        if not self.paper_trade_id:
            raise ValueError("paper_trade_id must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class OutcomeAttribution(TimestampedModel):
    """Backward-linking artifact from one paper outcome to its upstream lineage."""

    outcome_attribution_id: str = Field(description="Canonical outcome-attribution identifier.")
    trade_outcome_id: str = Field(description="Trade-outcome identifier.")
    paper_position_state_id: str = Field(description="Paper-position state identifier.")
    paper_trade_id: str = Field(description="Paper-trade identifier.")
    portfolio_proposal_id: str = Field(description="Parent portfolio-proposal identifier.")
    position_idea_id: str = Field(description="Parent position-idea identifier.")
    signal_id: str = Field(description="Linked signal identifier.")
    research_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Upstream research artifact identifiers informing the outcome path.",
    )
    feature_ids: list[str] = Field(
        default_factory=list,
        description="Feature identifiers linked through the motivating signal.",
    )
    portfolio_selection_summary_id: str | None = Field(
        default=None,
        description="Portfolio-selection summary identifier when available.",
    )
    construction_decision_id: str | None = Field(
        default=None,
        description="Construction-decision identifier when available.",
    )
    position_sizing_rationale_id: str | None = Field(
        default=None,
        description="Position-sizing rationale identifier when available.",
    )
    risk_check_ids: list[str] = Field(
        default_factory=list,
        description="Risk-check identifiers linked through the parent portfolio proposal.",
    )
    review_decision_ids: list[str] = Field(
        default_factory=list,
        description="Review-decision identifiers implicated in the trade path.",
    )
    review_note_ids: list[str] = Field(
        default_factory=list,
        description="Review-note identifiers implicated in the trade path.",
    )
    strategy_to_paper_mapping_id: str | None = Field(
        default=None,
        description="Strategy-to-paper mapping identifier when reconciliation had run.",
    )
    reconciliation_report_id: str | None = Field(
        default=None,
        description="Reconciliation-report identifier when reconciliation had run.",
    )
    summary: str = Field(description="Operator-readable summary of the backward linkage.")
    provenance: ProvenanceRecord = Field(description="Traceability for the outcome attribution.")

    @model_validator(mode="after")
    def validate_attribution(self) -> Self:
        """Require visible linkage and summary text."""

        if not self.trade_outcome_id:
            raise ValueError("trade_outcome_id must be non-empty.")
        if not self.paper_position_state_id:
            raise ValueError("paper_position_state_id must be non-empty.")
        if not self.paper_trade_id:
            raise ValueError("paper_trade_id must be non-empty.")
        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.position_idea_id:
            raise ValueError("position_idea_id must be non-empty.")
        if not self.signal_id:
            raise ValueError("signal_id must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ReviewFollowup(TimestampedModel):
    """Explicit post-trade followup item linked to one paper position or outcome."""

    review_followup_id: str = Field(description="Canonical review-followup identifier.")
    paper_trade_id: str = Field(description="Linked paper-trade identifier.")
    paper_position_state_id: str = Field(description="Linked paper-position state identifier.")
    trade_outcome_id: str | None = Field(
        default=None,
        description="Trade-outcome identifier that motivated the followup when applicable.",
    )
    status: ReviewFollowupStatus = Field(description="Followup lifecycle status.")
    instruction: str = Field(description="Concrete followup action the operator should take.")
    owner_id: str | None = Field(default=None, description="Optional owner for the followup.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Additional related artifact identifiers referenced by the followup.",
    )
    summary: str = Field(description="Operator-readable summary of the followup.")
    provenance: ProvenanceRecord = Field(description="Traceability for the followup.")

    @model_validator(mode="after")
    def validate_followup(self) -> Self:
        """Require visible linkage and instruction text."""

        if not self.paper_trade_id:
            raise ValueError("paper_trade_id must be non-empty.")
        if not self.paper_position_state_id:
            raise ValueError("paper_position_state_id must be non-empty.")
        if not self.instruction:
            raise ValueError("instruction must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class DailyPaperSummary(TimestampedModel):
    """One date-scoped summary of current paper positions and followups."""

    daily_paper_summary_id: str = Field(description="Canonical daily-paper summary identifier.")
    summary_date: date = Field(description="Date covered by the summary.")
    open_position_state_ids: list[str] = Field(
        default_factory=list,
        description="Open paper-position state identifiers included in the summary.",
    )
    closed_position_state_ids: list[str] = Field(
        default_factory=list,
        description="Closed paper-position state identifiers included in the summary.",
    )
    cancelled_position_state_ids: list[str] = Field(
        default_factory=list,
        description="Cancelled paper-position state identifiers included in the summary.",
    )
    lifecycle_event_ids: list[str] = Field(
        default_factory=list,
        description="Lifecycle-event identifiers included in the summary period.",
    )
    trade_outcome_ids: list[str] = Field(
        default_factory=list,
        description="Trade-outcome identifiers recorded for the summary period.",
    )
    open_review_followup_ids: list[str] = Field(
        default_factory=list,
        description="Open review-followup identifiers still requiring attention.",
    )
    open_position_count: int = Field(ge=0, description="Count of open paper positions.")
    closed_position_count: int = Field(ge=0, description="Count of closed paper positions.")
    cancelled_position_count: int = Field(ge=0, description="Count of cancelled paper positions.")
    aggregate_pnl_placeholder: PnLPlaceholder | None = Field(
        default=None,
        description="Optional aggregate placeholder PnL when coverage was sufficient.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes about coverage, incompleteness, or followups.",
    )
    summary: str = Field(description="Operator-readable summary of the daily paper book.")
    provenance: ProvenanceRecord = Field(description="Traceability for the daily paper summary.")

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        """Require explicit counts and summary text."""

        if self.open_position_count != len(self.open_position_state_ids):
            raise ValueError("open_position_count must match len(open_position_state_ids).")
        if self.closed_position_count != len(self.closed_position_state_ids):
            raise ValueError("closed_position_count must match len(closed_position_state_ids).")
        if self.cancelled_position_count != len(self.cancelled_position_state_ids):
            raise ValueError(
                "cancelled_position_count must match len(cancelled_position_state_ids)."
            )
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self
