from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.core import (
    build_provenance,
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    AuditOutcome,
    DailyPaperSummary,
    OutcomeAttribution,
    PaperLedgerEntry,
    PaperPositionState,
    PaperPositionStateStatus,
    PaperTrade,
    PaperTradeStatus,
    PnLPlaceholder,
    PortfolioProposal,
    PositionIdea,
    PositionLifecycleEvent,
    PositionLifecycleEventType,
    PositionSide,
    ReviewDecision,
    ReviewFollowup,
    ReviewFollowupStatus,
    ReviewTargetType,
    RiskWarningRelevance,
    RunSummary,
    Signal,
    StrictModel,
    ThesisAssessment,
    TradeOutcome,
    WorkflowStatus,
)
from libraries.utils import make_canonical_id, make_prefixed_id
from services.audit import AuditEventRequest, AuditLoggingService
from services.monitoring import MonitoringService, RecordRunSummaryRequest
from services.paper_ledger.loaders import LoadedPaperLedgerWorkspace, load_paper_ledger_workspace
from services.paper_ledger.storage import LocalPaperLedgerArtifactStore


class AdmitApprovedTradeRequest(StrictModel):
    """Request to admit one approved paper trade into the paper ledger."""

    paper_trade: PaperTrade = Field(description="Approved paper trade to admit.")
    portfolio_proposal: PortfolioProposal = Field(description="Parent portfolio proposal.")
    position_idea: PositionIdea = Field(description="Parent position idea.")
    signal: Signal = Field(description="Signal linked to the admitted trade.")
    requested_by: str = Field(description="Requester identifier.")
    related_review_decision: ReviewDecision | None = Field(
        default=None,
        description="Review decision that approved the trade when available.",
)

T = TypeVar("T")


class AdmitApprovedTradeResponse(StrictModel):
    """Artifacts recorded while admitting one approved paper trade."""

    updated_paper_trade: PaperTrade = Field(description="Updated paper trade with ledger linkage.")
    paper_position_state: PaperPositionState = Field(description="Created paper-position state.")
    position_lifecycle_event: PositionLifecycleEvent = Field(
        description="Created lifecycle event representing ledger admission."
    )
    paper_ledger_entry: PaperLedgerEntry = Field(description="Created initial ledger entry.")
    review_followups: list[ReviewFollowup] = Field(
        default_factory=list,
        description="Followups created because the admitted position is incomplete.",
    )
    run_summary: RunSummary | None = Field(
        default=None,
        description="Monitoring run summary recorded for the admission workflow.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RecordLifecycleEventRequest(StrictModel):
    """Request to record one follow-on lifecycle event for an admitted paper position."""

    paper_trade_id: str = Field(description="Paper-trade identifier.")
    paper_position_state_id: str | None = Field(
        default=None,
        description="Paper-position state identifier when already known.",
    )
    event_type: PositionLifecycleEventType = Field(description="Lifecycle event to record.")
    event_time: datetime = Field(description="UTC timestamp of the lifecycle event.")
    reference_price_usd: float | None = Field(
        default=None,
        gt=0.0,
        description="Reference price linked to the lifecycle event when available.",
    )
    quantity: float | None = Field(
        default=None,
        gt=0.0,
        description="Materialized quantity when this event updates quantity semantics.",
    )
    requested_by: str = Field(description="Requester identifier.")
    related_review_decision_id: str | None = Field(
        default=None,
        description="Review-decision identifier that motivated the event when applicable.",
    )
    notes: list[str] = Field(default_factory=list)


class RecordLifecycleEventResponse(StrictModel):
    """Artifacts recorded while applying one lifecycle event."""

    updated_paper_trade: PaperTrade = Field(description="Updated paper trade.")
    updated_paper_position_state: PaperPositionState = Field(
        description="Updated paper-position state."
    )
    position_lifecycle_event: PositionLifecycleEvent = Field(description="Persisted lifecycle event.")
    paper_ledger_entry: PaperLedgerEntry = Field(description="Persisted ledger entry.")
    run_summary: RunSummary | None = Field(default=None)
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RecordTradeOutcomeRequest(StrictModel):
    """Request to record one trade outcome and its backward attribution."""

    paper_trade_id: str = Field(description="Paper-trade identifier.")
    paper_position_state_id: str | None = Field(
        default=None,
        description="Paper-position state identifier when already known.",
    )
    thesis_assessment: ThesisAssessment = Field(description="Human-authored thesis assessment.")
    risk_warning_relevance: RiskWarningRelevance = Field(
        description="Human-authored assessment of whether prior risk warnings mattered."
    )
    assumption_notes: list[str] = Field(default_factory=list)
    learning_notes: list[str] = Field(default_factory=list)
    followup_instructions: list[str] = Field(default_factory=list)
    requested_by: str = Field(description="Requester identifier.")


class RecordTradeOutcomeResponse(StrictModel):
    """Artifacts recorded while posting one trade outcome."""

    updated_paper_trade: PaperTrade = Field(description="Updated paper trade.")
    updated_paper_position_state: PaperPositionState = Field(
        description="Updated paper-position state."
    )
    trade_outcome: TradeOutcome = Field(description="Persisted trade outcome.")
    outcome_attribution: OutcomeAttribution = Field(description="Persisted outcome attribution.")
    review_followups: list[ReviewFollowup] = Field(default_factory=list)
    run_summary: RunSummary | None = Field(default=None)
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GenerateDailyPaperSummaryRequest(StrictModel):
    """Request to summarize the current local paper book for one date."""

    summary_date: date = Field(description="Date covered by the summary.")
    requested_by: str = Field(description="Requester identifier.")
    reference_marks_by_symbol: dict[str, float] = Field(
        default_factory=dict,
        description="Optional symbol-to-mark mapping used for placeholder daily book marks.",
    )


class GenerateDailyPaperSummaryResponse(StrictModel):
    """Artifacts recorded while generating one daily paper summary."""

    daily_paper_summary: DailyPaperSummary = Field(description="Persisted daily paper summary.")
    run_summary: RunSummary | None = Field(default=None)
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PaperLedgerService(BaseService):
    """Track admitted paper positions, their lifecycle, and post-trade outcomes."""

    capability_name = "paper_ledger"
    capability_description = (
        "Tracks approved paper trades as admitted ledger states, lifecycle events, summaries, and outcomes."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PaperTrade", "PortfolioProposal", "manual lifecycle events"],
            produces=[
                "PaperPositionState",
                "PaperLedgerEntry",
                "PositionLifecycleEvent",
                "TradeOutcome",
                "DailyPaperSummary",
            ],
            api_routes=[],
        )

    def admit_approved_trade(
        self,
        request: AdmitApprovedTradeRequest,
        *,
        output_root: Path | None = None,
    ) -> AdmitApprovedTradeResponse:
        """Admit one approved paper trade into the paper ledger."""

        portfolio_root, monitoring_root, audit_root, _signal_root, _review_root = self._resolve_roots(
            output_root
        )
        now = self.clock.now()
        trade = request.paper_trade
        if trade.status is not PaperTradeStatus.APPROVED:
            raise ValueError("Only approved paper trades can be admitted into the paper ledger.")
        if request.portfolio_proposal.portfolio_proposal_id != trade.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must match the admitted paper trade.")
        if request.position_idea.position_idea_id != trade.position_idea_id:
            raise ValueError("position_idea_id must match the admitted paper trade.")
        if request.signal.signal_id != request.position_idea.signal_id:
            raise ValueError("signal_id must match the parent position idea signal.")
        if trade.paper_position_state_id is not None:
            raise ValueError("This paper trade has already been admitted into the paper ledger.")

        approval_time = trade.approved_at or now
        state_id = make_canonical_id("ppos", trade.paper_trade_id)
        event_id = make_canonical_id(
            "plevt", trade.paper_trade_id, PositionLifecycleEventType.APPROVAL_ADMITTED.value
        )
        entry_id = make_canonical_id(
            "pledger", trade.paper_trade_id, PositionLifecycleEventType.APPROVAL_ADMITTED.value
        )

        followups: list[ReviewFollowup] = []
        followup_ids: list[str] = []
        notes: list[str] = []
        if trade.quantity is None or trade.assumed_reference_price_usd is None:
            followup = ReviewFollowup(
                review_followup_id=make_canonical_id("rfup", trade.paper_trade_id, "materialization"),
                paper_trade_id=trade.paper_trade_id,
                paper_position_state_id=state_id,
                trade_outcome_id=None,
                status=ReviewFollowupStatus.OPEN,
                instruction=(
                    "Supply a reference price and materialized quantity before relying on placeholder PnL tracking."
                ),
                owner_id=None,
                related_artifact_ids=[
                    trade.paper_trade_id,
                    request.portfolio_proposal.portfolio_proposal_id,
                    request.position_idea.position_idea_id,
                    request.signal.signal_id,
                ],
                summary="Paper position admitted with incomplete quantity or entry-price materialization.",
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="paper_ledger_materialization_followup",
                    upstream_artifact_ids=[
                        trade.paper_trade_id,
                        request.portfolio_proposal.portfolio_proposal_id,
                        request.position_idea.position_idea_id,
                        request.signal.signal_id,
                    ],
                    notes=["reason=incomplete_materialization"],
                ),
                created_at=now,
                updated_at=now,
            )
            followups.append(followup)
            followup_ids.append(followup.review_followup_id)
            notes.append("materialization_incomplete")

        state = PaperPositionState(
            paper_position_state_id=state_id,
            paper_trade_id=trade.paper_trade_id,
            portfolio_proposal_id=request.portfolio_proposal.portfolio_proposal_id,
            position_idea_id=request.position_idea.position_idea_id,
            signal_id=request.signal.signal_id,
            company_id=request.position_idea.company_id,
            symbol=trade.symbol,
            side=trade.side,
            state=PaperPositionStateStatus.APPROVED_PENDING_FILL,
            opened_at=None,
            closed_at=None,
            quantity=trade.quantity,
            entry_reference_price_usd=trade.assumed_reference_price_usd,
            latest_reference_price_usd=trade.assumed_reference_price_usd,
            latest_pnl_placeholder=None,
            latest_lifecycle_event_id=event_id,
            latest_ledger_entry_id=entry_id,
            review_followup_ids=followup_ids,
            trade_outcome_ids=[],
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="paper_ledger_admission",
                source_reference_ids=trade.provenance.source_reference_ids,
                upstream_artifact_ids=[
                    trade.paper_trade_id,
                    request.portfolio_proposal.portfolio_proposal_id,
                    request.position_idea.position_idea_id,
                    request.signal.signal_id,
                    *(
                        [request.related_review_decision.review_decision_id]
                        if request.related_review_decision is not None
                        else []
                    ),
                ],
                notes=["state=approved_pending_fill"],
            ),
            created_at=now,
            updated_at=now,
        )
        lifecycle_event = PositionLifecycleEvent(
            position_lifecycle_event_id=event_id,
            paper_position_state_id=state_id,
            paper_trade_id=trade.paper_trade_id,
            event_type=PositionLifecycleEventType.APPROVAL_ADMITTED,
            prior_state=None,
            new_state=PaperPositionStateStatus.APPROVED_PENDING_FILL,
            happened_at=approval_time,
            related_artifact_ids=[
                trade.paper_trade_id,
                request.portfolio_proposal.portfolio_proposal_id,
                request.position_idea.position_idea_id,
                request.signal.signal_id,
                *followup_ids,
                *(
                    [request.related_review_decision.review_decision_id]
                    if request.related_review_decision is not None
                    else []
                ),
            ],
            summary="Approved paper trade admitted into the paper ledger.",
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="paper_ledger_lifecycle_event",
                source_reference_ids=trade.provenance.source_reference_ids,
                upstream_artifact_ids=[trade.paper_trade_id, state_id],
                notes=["event_type=approval_admitted"],
            ),
            created_at=now,
            updated_at=now,
        )
        ledger_entry = PaperLedgerEntry(
            paper_ledger_entry_id=entry_id,
            paper_position_state_id=state_id,
            paper_trade_id=trade.paper_trade_id,
            entry_kind=PositionLifecycleEventType.APPROVAL_ADMITTED,
            event_time=approval_time,
            reference_price_usd=trade.assumed_reference_price_usd,
            quantity_delta=trade.quantity,
            notional_delta_usd=trade.notional_usd,
            pnl_placeholder=None,
            related_lifecycle_event_id=event_id,
            related_review_decision_id=(
                request.related_review_decision.review_decision_id
                if request.related_review_decision is not None
                else None
            ),
            related_artifact_ids=[
                trade.paper_trade_id,
                request.portfolio_proposal.portfolio_proposal_id,
                request.position_idea.position_idea_id,
                request.signal.signal_id,
                *followup_ids,
            ],
            summary="Initial paper-ledger admission entry for the approved trade.",
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="paper_ledger_entry",
                source_reference_ids=trade.provenance.source_reference_ids,
                upstream_artifact_ids=[trade.paper_trade_id, state_id, event_id],
                notes=["entry_kind=approval_admitted"],
            ),
            created_at=now,
            updated_at=now,
        )
        updated_trade = trade.model_copy(
            update={
                "paper_position_state_id": state_id,
                "execution_notes": [
                    *trade.execution_notes,
                    "paper_trade_admitted_to_ledger=true",
                    f"paper_position_state_id={state_id}",
                ],
                "updated_at": now,
            }
        )

        store = LocalPaperLedgerArtifactStore(root=portfolio_root, clock=self.clock)
        storage_locations = self._persist_trade_and_ledger_artifacts(
            store=store,
            paper_trade=updated_trade,
            paper_position_state=state,
            paper_ledger_entry=ledger_entry,
            position_lifecycle_event=lifecycle_event,
            review_followups=followups,
        )
        audit_response = self._audit_service().record_event(
            AuditEventRequest(
                event_type="paper_trade_admitted_to_ledger",
                actor_type="service",
                actor_id=self.capability_name,
                target_type="paper_trade",
                target_id=updated_trade.paper_trade_id,
                action="admit_approved_trade",
                outcome=AuditOutcome.SUCCESS,
                reason="Approved paper trade admitted into the local paper ledger.",
                status_before=trade.status.value,
                status_after=updated_trade.status.value,
                related_artifact_ids=[
                    state.paper_position_state_id,
                    lifecycle_event.position_lifecycle_event_id,
                    ledger_entry.paper_ledger_entry_id,
                    *followup_ids,
                ],
                notes=notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        run_summary = self._record_run_summary(
            workflow_name="paper_ledger_admission",
            workflow_run_id=state.paper_position_state_id,
            requested_by=request.requested_by,
            status=WorkflowStatus.ATTENTION_REQUIRED if followups else WorkflowStatus.SUCCEEDED,
            started_at=now,
            completed_at=self.clock.now(),
            storage_locations=storage_locations,
            produced_artifact_ids=[
                updated_trade.paper_trade_id,
                state.paper_position_state_id,
                lifecycle_event.position_lifecycle_event_id,
                ledger_entry.paper_ledger_entry_id,
                *followup_ids,
            ],
            attention_reasons=(
                ["paper_position_materialization_incomplete"] if followups else []
            ),
            notes=notes,
            output_root=monitoring_root,
        )
        return AdmitApprovedTradeResponse(
            updated_paper_trade=updated_trade,
            paper_position_state=state,
            position_lifecycle_event=lifecycle_event,
            paper_ledger_entry=ledger_entry,
            review_followups=followups,
            run_summary=run_summary,
            storage_locations=storage_locations,
            notes=notes,
        )

    def record_lifecycle_event(
        self,
        request: RecordLifecycleEventRequest,
        *,
        output_root: Path | None = None,
    ) -> RecordLifecycleEventResponse:
        """Record one follow-on lifecycle event for an admitted paper position."""

        portfolio_root, monitoring_root, audit_root, signal_root, review_root = self._resolve_roots(
            output_root
        )
        workspace = load_paper_ledger_workspace(
            portfolio_root=portfolio_root,
            signal_root=signal_root,
            review_root=review_root,
        )
        trade, state = self._resolve_trade_and_state(
            workspace=workspace,
            paper_trade_id=request.paper_trade_id,
            paper_position_state_id=request.paper_position_state_id,
        )
        if request.event_type is PositionLifecycleEventType.APPROVAL_ADMITTED:
            raise ValueError("approval_admitted should be recorded through admit_approved_trade().")
        if state.state in {
            PaperPositionStateStatus.CLOSED,
            PaperPositionStateStatus.CANCELLED,
        }:
            raise ValueError("Terminal paper positions cannot accept additional lifecycle events.")

        now = self.clock.now()
        prior_state = state.state
        new_state = self._new_state_from_event(prior_state=prior_state, event_type=request.event_type)
        quantity = request.quantity if request.quantity is not None else state.quantity
        latest_reference_price = (
            request.reference_price_usd
            if request.reference_price_usd is not None
            else state.latest_reference_price_usd
        )
        placeholder = self._build_placeholder_for_event(
            side=trade.side,
            quantity=quantity,
            entry_reference_price_usd=state.entry_reference_price_usd,
            current_or_exit_price_usd=request.reference_price_usd,
            event_type=request.event_type,
        )
        event_id = make_canonical_id(
            "plevt",
            trade.paper_trade_id,
            request.event_type.value,
            request.event_time.isoformat(),
        )
        entry_id = make_canonical_id(
            "pledger",
            trade.paper_trade_id,
            request.event_type.value,
            request.event_time.isoformat(),
        )
        updated_state = state.model_copy(
            update={
                "state": new_state,
                "opened_at": (
                    request.event_time
                    if new_state is PaperPositionStateStatus.OPEN and state.opened_at is None
                    else state.opened_at
                ),
                "closed_at": (
                    request.event_time
                    if new_state
                    in {PaperPositionStateStatus.CLOSED, PaperPositionStateStatus.CANCELLED}
                    else state.closed_at
                ),
                "quantity": quantity,
                "latest_reference_price_usd": latest_reference_price,
                "latest_pnl_placeholder": placeholder or state.latest_pnl_placeholder,
                "latest_lifecycle_event_id": event_id,
                "latest_ledger_entry_id": entry_id,
                "updated_at": now,
            }
        )
        lifecycle_event = PositionLifecycleEvent(
            position_lifecycle_event_id=event_id,
            paper_position_state_id=state.paper_position_state_id,
            paper_trade_id=trade.paper_trade_id,
            event_type=request.event_type,
            prior_state=prior_state,
            new_state=new_state,
            happened_at=request.event_time,
            related_artifact_ids=[trade.paper_trade_id, state.paper_position_state_id],
            summary=self._lifecycle_summary(request.event_type, trade.symbol),
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="paper_ledger_lifecycle_event",
                source_reference_ids=trade.provenance.source_reference_ids,
                upstream_artifact_ids=[trade.paper_trade_id, state.paper_position_state_id],
                notes=[f"event_type={request.event_type.value}", *request.notes],
            ),
            created_at=now,
            updated_at=now,
        )
        quantity_delta, notional_delta = self._ledger_deltas_for_event(
            event_type=request.event_type,
            prior_quantity=state.quantity,
            new_quantity=quantity,
            reference_price_usd=request.reference_price_usd,
        )
        ledger_entry = PaperLedgerEntry(
            paper_ledger_entry_id=entry_id,
            paper_position_state_id=state.paper_position_state_id,
            paper_trade_id=trade.paper_trade_id,
            entry_kind=request.event_type,
            event_time=request.event_time,
            reference_price_usd=request.reference_price_usd,
            quantity_delta=quantity_delta,
            notional_delta_usd=notional_delta,
            pnl_placeholder=placeholder,
            related_lifecycle_event_id=event_id,
            related_review_decision_id=request.related_review_decision_id,
            related_artifact_ids=[trade.paper_trade_id, state.paper_position_state_id],
            summary=self._ledger_summary(request.event_type, trade.symbol),
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="paper_ledger_entry",
                source_reference_ids=trade.provenance.source_reference_ids,
                upstream_artifact_ids=[trade.paper_trade_id, state.paper_position_state_id, event_id],
                notes=[f"entry_kind={request.event_type.value}", *request.notes],
            ),
            created_at=now,
            updated_at=now,
        )

        updated_trade = self._update_trade_for_lifecycle_event(
            paper_trade=trade,
            event_type=request.event_type,
            event_time=request.event_time,
            paper_position_state_id=state.paper_position_state_id,
            lifecycle_event_id=event_id,
        )
        store = LocalPaperLedgerArtifactStore(root=portfolio_root, clock=self.clock)
        storage_locations = self._persist_trade_and_ledger_artifacts(
            store=store,
            paper_trade=updated_trade,
            paper_position_state=updated_state,
            paper_ledger_entry=ledger_entry,
            position_lifecycle_event=lifecycle_event,
            review_followups=[],
        )
        audit_response = self._audit_service().record_event(
            AuditEventRequest(
                event_type="paper_position_lifecycle_event_recorded",
                actor_type="service",
                actor_id=self.capability_name,
                target_type="paper_trade",
                target_id=updated_trade.paper_trade_id,
                action=request.event_type.value,
                outcome=AuditOutcome.SUCCESS,
                reason=self._lifecycle_summary(request.event_type, trade.symbol),
                status_before=trade.status.value,
                status_after=updated_trade.status.value,
                related_artifact_ids=[
                    updated_state.paper_position_state_id,
                    lifecycle_event.position_lifecycle_event_id,
                    ledger_entry.paper_ledger_entry_id,
                ],
                notes=request.notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        notes = list(request.notes)
        attention_reasons = []
        if placeholder is not None and not placeholder.complete:
            notes.append("placeholder_pnl_incomplete")
            attention_reasons.append("paper_position_missing_mark_or_materialization")
        run_summary = self._record_run_summary(
            workflow_name="paper_position_lifecycle",
            workflow_run_id=event_id,
            requested_by=request.requested_by,
            status=WorkflowStatus.ATTENTION_REQUIRED if attention_reasons else WorkflowStatus.SUCCEEDED,
            started_at=now,
            completed_at=self.clock.now(),
            storage_locations=storage_locations,
            produced_artifact_ids=[
                updated_trade.paper_trade_id,
                updated_state.paper_position_state_id,
                lifecycle_event.position_lifecycle_event_id,
                ledger_entry.paper_ledger_entry_id,
            ],
            attention_reasons=attention_reasons,
            notes=notes,
            output_root=monitoring_root,
        )
        return RecordLifecycleEventResponse(
            updated_paper_trade=updated_trade,
            updated_paper_position_state=updated_state,
            position_lifecycle_event=lifecycle_event,
            paper_ledger_entry=ledger_entry,
            run_summary=run_summary,
            storage_locations=storage_locations,
            notes=notes,
        )

    def record_trade_outcome(
        self,
        request: RecordTradeOutcomeRequest,
        *,
        output_root: Path | None = None,
    ) -> RecordTradeOutcomeResponse:
        """Record one trade outcome and its backward-linking attribution."""

        portfolio_root, monitoring_root, audit_root, signal_root, review_root = self._resolve_roots(
            output_root
        )
        workspace = load_paper_ledger_workspace(
            portfolio_root=portfolio_root,
            signal_root=signal_root,
            review_root=review_root,
        )
        trade, state = self._resolve_trade_and_state(
            workspace=workspace,
            paper_trade_id=request.paper_trade_id,
            paper_position_state_id=request.paper_position_state_id,
        )
        if state.state not in {
            PaperPositionStateStatus.CLOSED,
            PaperPositionStateStatus.CANCELLED,
        }:
            raise ValueError("Trade outcomes can only be recorded for closed or cancelled paper positions.")

        proposal = self._require_target(workspace.portfolio_proposals_by_id, trade.portfolio_proposal_id)
        position_idea = self._require_target(workspace.position_ideas_by_id, trade.position_idea_id)
        signal = self._require_target(workspace.signals_by_id, position_idea.signal_id)

        now = self.clock.now()
        outcome = TradeOutcome(
            trade_outcome_id=make_prefixed_id("tout"),
            paper_position_state_id=state.paper_position_state_id,
            paper_trade_id=trade.paper_trade_id,
            thesis_assessment=request.thesis_assessment,
            risk_warning_relevance=request.risk_warning_relevance,
            assumption_notes=request.assumption_notes,
            learning_notes=request.learning_notes,
            pnl_placeholder=state.latest_pnl_placeholder,
            summary=(
                f"Trade outcome recorded with thesis assessment `{request.thesis_assessment.value}` "
                f"and risk-warning relevance `{request.risk_warning_relevance.value}`."
            ),
            provenance=build_provenance(
                clock=self.clock,
                source_reference_ids=trade.provenance.source_reference_ids,
                transformation_name="paper_trade_outcome_recording",
                upstream_artifact_ids=[
                    trade.paper_trade_id,
                    state.paper_position_state_id,
                    proposal.portfolio_proposal_id,
                    position_idea.position_idea_id,
                    signal.signal_id,
                ],
                notes=[
                    f"thesis_assessment={request.thesis_assessment.value}",
                    f"risk_warning_relevance={request.risk_warning_relevance.value}",
                ],
            ),
            created_at=now,
            updated_at=now,
        )
        attribution = self._build_outcome_attribution(
            workspace=workspace,
            trade=trade,
            state=state,
            proposal=proposal,
            position_idea=position_idea,
            signal=signal,
            outcome=outcome,
            now=now,
        )
        followups = self._build_followups_for_outcome(
            trade=trade,
            state=state,
            outcome=outcome,
            instructions=request.followup_instructions,
            now=now,
        )
        updated_state = state.model_copy(
            update={
                "trade_outcome_ids": [*state.trade_outcome_ids, outcome.trade_outcome_id],
                "review_followup_ids": [
                    *state.review_followup_ids,
                    *[followup.review_followup_id for followup in followups],
                ],
                "updated_at": now,
            }
        )
        updated_trade = trade.model_copy(
            update={
                "latest_trade_outcome_id": outcome.trade_outcome_id,
                "updated_at": now,
            }
        )
        store = LocalPaperLedgerArtifactStore(root=portfolio_root, clock=self.clock)
        storage_locations = [
            store.persist_model(
                artifact_id=updated_trade.paper_trade_id,
                category="paper_trades",
                model=updated_trade,
                source_reference_ids=updated_trade.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=updated_state.paper_position_state_id,
                category="paper_position_states",
                model=updated_state,
                source_reference_ids=updated_state.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=outcome.trade_outcome_id,
                category="trade_outcomes",
                model=outcome,
                source_reference_ids=outcome.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=attribution.outcome_attribution_id,
                category="outcome_attributions",
                model=attribution,
                source_reference_ids=attribution.provenance.source_reference_ids,
            ),
        ]
        for followup in followups:
            storage_locations.append(
                store.persist_model(
                    artifact_id=followup.review_followup_id,
                    category="review_followups",
                    model=followup,
                    source_reference_ids=followup.provenance.source_reference_ids,
                )
            )
        audit_response = self._audit_service().record_event(
            AuditEventRequest(
                event_type="paper_trade_outcome_recorded",
                actor_type="service",
                actor_id=self.capability_name,
                target_type="paper_trade",
                target_id=updated_trade.paper_trade_id,
                action="record_trade_outcome",
                outcome=AuditOutcome.SUCCESS,
                reason=outcome.summary,
                status_before=trade.status.value,
                status_after=updated_trade.status.value,
                related_artifact_ids=[
                    updated_state.paper_position_state_id,
                    outcome.trade_outcome_id,
                    attribution.outcome_attribution_id,
                    *[followup.review_followup_id for followup in followups],
                ],
                notes=request.learning_notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        attention_reasons = ["open_review_followups"] if followups else []
        notes = [f"thesis_assessment={request.thesis_assessment.value}"]
        run_summary = self._record_run_summary(
            workflow_name="paper_trade_outcome",
            workflow_run_id=outcome.trade_outcome_id,
            requested_by=request.requested_by,
            status=WorkflowStatus.ATTENTION_REQUIRED if followups else WorkflowStatus.SUCCEEDED,
            started_at=now,
            completed_at=self.clock.now(),
            storage_locations=storage_locations,
            produced_artifact_ids=[
                updated_trade.paper_trade_id,
                updated_state.paper_position_state_id,
                outcome.trade_outcome_id,
                attribution.outcome_attribution_id,
                *[followup.review_followup_id for followup in followups],
            ],
            attention_reasons=attention_reasons,
            notes=notes,
            output_root=monitoring_root,
        )
        return RecordTradeOutcomeResponse(
            updated_paper_trade=updated_trade,
            updated_paper_position_state=updated_state,
            trade_outcome=outcome,
            outcome_attribution=attribution,
            review_followups=followups,
            run_summary=run_summary,
            storage_locations=storage_locations,
            notes=notes,
        )

    def generate_daily_paper_summary(
        self,
        request: GenerateDailyPaperSummaryRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateDailyPaperSummaryResponse:
        """Generate one local daily summary of the current paper book."""

        portfolio_root, monitoring_root, audit_root, signal_root, review_root = self._resolve_roots(
            output_root
        )
        workspace = load_paper_ledger_workspace(
            portfolio_root=portfolio_root,
            signal_root=signal_root,
            review_root=review_root,
        )
        now = self.clock.now()
        states = list(workspace.paper_position_states_by_id.values())
        open_states = [
            state for state in states if state.state is PaperPositionStateStatus.OPEN
        ]
        closed_states = [
            state for state in states if state.state is PaperPositionStateStatus.CLOSED
        ]
        cancelled_states = [
            state for state in states if state.state is PaperPositionStateStatus.CANCELLED
        ]
        lifecycle_event_ids = [
            event.position_lifecycle_event_id
            for events in workspace.position_lifecycle_events_by_state_id.values()
            for event in events
            if event.happened_at.date() == request.summary_date
        ]
        trade_outcome_ids = [
            outcome.trade_outcome_id
            for outcome in workspace.trade_outcomes_by_id.values()
            if outcome.created_at.date() == request.summary_date
        ]
        open_followups = [
            followup
            for followups in workspace.review_followups_by_state_id.values()
            for followup in followups
            if followup.status is ReviewFollowupStatus.OPEN
        ]
        aggregate_placeholder, aggregate_notes = self._aggregate_daily_placeholder(
            open_states=open_states,
            reference_marks_by_symbol=request.reference_marks_by_symbol,
        )
        summary_notes = list(aggregate_notes)
        summary = DailyPaperSummary(
            daily_paper_summary_id=make_canonical_id("pday", request.summary_date.isoformat()),
            summary_date=request.summary_date,
            open_position_state_ids=[state.paper_position_state_id for state in open_states],
            closed_position_state_ids=[state.paper_position_state_id for state in closed_states],
            cancelled_position_state_ids=[state.paper_position_state_id for state in cancelled_states],
            lifecycle_event_ids=lifecycle_event_ids,
            trade_outcome_ids=trade_outcome_ids,
            open_review_followup_ids=[followup.review_followup_id for followup in open_followups],
            open_position_count=len(open_states),
            closed_position_count=len(closed_states),
            cancelled_position_count=len(cancelled_states),
            aggregate_pnl_placeholder=aggregate_placeholder,
            notes=summary_notes,
            summary=(
                f"Daily paper summary for {request.summary_date.isoformat()} with "
                f"{len(open_states)} open, {len(closed_states)} closed, and "
                f"{len(cancelled_states)} cancelled paper positions."
            ),
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="daily_paper_summary_generation",
                upstream_artifact_ids=[
                    *[state.paper_position_state_id for state in open_states],
                    *[state.paper_position_state_id for state in closed_states],
                    *[state.paper_position_state_id for state in cancelled_states],
                    *lifecycle_event_ids,
                    *trade_outcome_ids,
                    *[followup.review_followup_id for followup in open_followups],
                ],
                notes=summary_notes,
            ),
            created_at=now,
            updated_at=now,
        )
        store = LocalPaperLedgerArtifactStore(root=portfolio_root, clock=self.clock)
        storage_locations = [
            store.persist_model(
                artifact_id=summary.daily_paper_summary_id,
                category="daily_paper_summaries",
                model=summary,
                source_reference_ids=summary.provenance.source_reference_ids,
            )
        ]
        audit_response = self._audit_service().record_event(
            AuditEventRequest(
                event_type="daily_paper_summary_created",
                actor_type="service",
                actor_id=self.capability_name,
                target_type="daily_paper_summary",
                target_id=summary.daily_paper_summary_id,
                action="generate_daily_paper_summary",
                outcome=AuditOutcome.SUCCESS,
                reason=summary.summary,
                related_artifact_ids=[
                    *summary.open_position_state_ids,
                    *summary.closed_position_state_ids,
                    *summary.cancelled_position_state_ids,
                    *summary.trade_outcome_ids,
                ],
                notes=summary.notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        attention_reasons: list[str] = []
        if aggregate_placeholder is None and open_states:
            attention_reasons.append("open_positions_missing_mark_coverage")
        if open_followups:
            attention_reasons.append("open_review_followups")
        closed_without_outcome = [
            state.paper_position_state_id
            for state in closed_states
            if not state.trade_outcome_ids
        ]
        if closed_without_outcome:
            attention_reasons.append("closed_positions_missing_trade_outcome")
            summary.notes.append("closed_positions_missing_trade_outcome")
        run_summary = self._record_run_summary(
            workflow_name="daily_paper_summary",
            workflow_run_id=summary.daily_paper_summary_id,
            requested_by=request.requested_by,
            status=WorkflowStatus.ATTENTION_REQUIRED if attention_reasons else WorkflowStatus.SUCCEEDED,
            started_at=now,
            completed_at=self.clock.now(),
            storage_locations=storage_locations,
            produced_artifact_ids=[summary.daily_paper_summary_id],
            attention_reasons=attention_reasons,
            notes=summary.notes,
            output_root=monitoring_root,
        )
        return GenerateDailyPaperSummaryResponse(
            daily_paper_summary=summary,
            run_summary=run_summary,
            storage_locations=storage_locations,
            notes=summary.notes,
        )

    def _resolve_roots(self, output_root: Path | None) -> tuple[Path, Path, Path, Path, Path]:
        """Resolve the portfolio, monitoring, audit, signal, and review roots."""

        if output_root is None:
            workspace = resolve_artifact_workspace()
            return (
                workspace.portfolio_root,
                workspace.monitoring_root,
                workspace.audit_root,
                workspace.signal_root,
                workspace.review_root,
            )
        workspace = resolve_artifact_workspace_from_stage_root(output_root)
        return (
            output_root,
            workspace.monitoring_root,
            workspace.audit_root,
            workspace.signal_root,
            workspace.review_root,
        )

    def _resolve_trade_and_state(
        self,
        *,
        workspace: LoadedPaperLedgerWorkspace,
        paper_trade_id: str,
        paper_position_state_id: str | None,
    ) -> tuple[PaperTrade, PaperPositionState]:
        trade = self._require_target(workspace.paper_trades_by_id, paper_trade_id)
        resolved_state_id = paper_position_state_id or trade.paper_position_state_id
        if resolved_state_id is None:
            raise ValueError("paper_position_state_id is required when the paper trade has not been admitted.")
        state = self._require_target(workspace.paper_position_states_by_id, resolved_state_id)
        if state.paper_trade_id != trade.paper_trade_id:
            raise ValueError("paper_position_state_id does not belong to the requested paper trade.")
        return trade, state

    def _new_state_from_event(
        self,
        *,
        prior_state: PaperPositionStateStatus,
        event_type: PositionLifecycleEventType,
    ) -> PaperPositionStateStatus:
        if event_type is PositionLifecycleEventType.SIMULATED_FILL_PLACEHOLDER:
            return PaperPositionStateStatus.OPEN
        if event_type is PositionLifecycleEventType.MARK_UPDATED:
            return (
                PaperPositionStateStatus.OPEN
                if prior_state is PaperPositionStateStatus.APPROVED_PENDING_FILL
                else prior_state
            )
        if event_type is PositionLifecycleEventType.CLOSED:
            return PaperPositionStateStatus.CLOSED
        if event_type is PositionLifecycleEventType.CANCELLED:
            return PaperPositionStateStatus.CANCELLED
        return prior_state

    def _build_placeholder_for_event(
        self,
        *,
        side: PositionSide,
        quantity: float | None,
        entry_reference_price_usd: float | None,
        current_or_exit_price_usd: float | None,
        event_type: PositionLifecycleEventType,
    ) -> PnLPlaceholder | None:
        if current_or_exit_price_usd is None:
            return None
        if quantity is None or entry_reference_price_usd is None:
            return PnLPlaceholder(
                entry_reference_price_usd=entry_reference_price_usd,
                current_or_exit_price_usd=current_or_exit_price_usd,
                unrealized_pnl_usd=None,
                realized_pnl_usd=None,
                complete=False,
                calculation_basis=f"side_aware_reference_mark::{event_type.value}",
                notes=["quantity_or_entry_reference_missing"],
            )
        price_move = current_or_exit_price_usd - entry_reference_price_usd
        signed_move = price_move if side is PositionSide.LONG else -price_move
        pnl = quantity * signed_move
        if event_type is PositionLifecycleEventType.CLOSED:
            return PnLPlaceholder(
                entry_reference_price_usd=entry_reference_price_usd,
                current_or_exit_price_usd=current_or_exit_price_usd,
                unrealized_pnl_usd=None,
                realized_pnl_usd=pnl,
                complete=True,
                calculation_basis="side_aware_reference_close",
                notes=[],
            )
        return PnLPlaceholder(
            entry_reference_price_usd=entry_reference_price_usd,
            current_or_exit_price_usd=current_or_exit_price_usd,
            unrealized_pnl_usd=pnl,
            realized_pnl_usd=None,
            complete=True,
            calculation_basis="side_aware_reference_mark",
            notes=[],
        )

    def _ledger_deltas_for_event(
        self,
        *,
        event_type: PositionLifecycleEventType,
        prior_quantity: float | None,
        new_quantity: float | None,
        reference_price_usd: float | None,
    ) -> tuple[float | None, float | None]:
        if event_type is PositionLifecycleEventType.SIMULATED_FILL_PLACEHOLDER:
            quantity_delta = (
                new_quantity - prior_quantity
                if new_quantity is not None and prior_quantity is not None
                else new_quantity
            )
            notional_delta = (
                quantity_delta * reference_price_usd
                if quantity_delta is not None and reference_price_usd is not None
                else None
            )
            return quantity_delta, notional_delta
        if event_type is PositionLifecycleEventType.CLOSED:
            quantity_delta = -prior_quantity if prior_quantity is not None else None
            notional_delta = (
                quantity_delta * reference_price_usd
                if quantity_delta is not None and reference_price_usd is not None
                else None
            )
            return quantity_delta, notional_delta
        return None, None

    def _update_trade_for_lifecycle_event(
        self,
        *,
        paper_trade: PaperTrade,
        event_type: PositionLifecycleEventType,
        event_time: datetime,
        paper_position_state_id: str,
        lifecycle_event_id: str,
    ) -> PaperTrade:
        updates: dict[str, object] = {
            "paper_position_state_id": paper_position_state_id,
            "execution_notes": [
                *paper_trade.execution_notes,
                f"paper_position_lifecycle_event_id={lifecycle_event_id}",
            ],
            "updated_at": self.clock.now(),
        }
        if event_type is PositionLifecycleEventType.SIMULATED_FILL_PLACEHOLDER:
            updates["status"] = PaperTradeStatus.SIMULATED
            updates["simulated_fill_at"] = event_time
        elif event_type is PositionLifecycleEventType.CANCELLED:
            updates["status"] = PaperTradeStatus.CANCELLED
        return paper_trade.model_copy(update=updates)

    def _build_outcome_attribution(
        self,
        *,
        workspace: LoadedPaperLedgerWorkspace,
        trade: PaperTrade,
        state: PaperPositionState,
        proposal: PortfolioProposal,
        position_idea: PositionIdea,
        signal: Signal,
        outcome: TradeOutcome,
        now: datetime,
    ) -> OutcomeAttribution:
        proposal_key = f"{ReviewTargetType.PORTFOLIO_PROPOSAL.value}::{proposal.portfolio_proposal_id}"
        trade_key = f"{ReviewTargetType.PAPER_TRADE.value}::{trade.paper_trade_id}"
        note_ids = [
            *[
                note.review_note_id
                for note in workspace.review_notes_by_target_key.get(proposal_key, [])
            ],
            *[
                note.review_note_id
                for note in workspace.review_notes_by_target_key.get(trade_key, [])
            ],
        ]
        return OutcomeAttribution(
            outcome_attribution_id=make_prefixed_id("oattr"),
            trade_outcome_id=outcome.trade_outcome_id,
            paper_position_state_id=state.paper_position_state_id,
            paper_trade_id=trade.paper_trade_id,
            portfolio_proposal_id=proposal.portfolio_proposal_id,
            position_idea_id=position_idea.position_idea_id,
            signal_id=signal.signal_id,
            research_artifact_ids=position_idea.research_artifact_ids,
            feature_ids=signal.feature_ids,
            portfolio_selection_summary_id=proposal.portfolio_selection_summary_id,
            construction_decision_id=position_idea.construction_decision_id,
            position_sizing_rationale_id=position_idea.position_sizing_rationale_id,
            risk_check_ids=[risk_check.risk_check_id for risk_check in proposal.risk_checks],
            review_decision_ids=[
                *proposal.review_decision_ids,
                *trade.review_decision_ids,
            ],
            review_note_ids=note_ids,
            strategy_to_paper_mapping_id=proposal.strategy_to_paper_mapping_id,
            reconciliation_report_id=proposal.reconciliation_report_id,
            summary=(
                "Outcome linked back to proposal, signal, construction, risk, review, and reconciliation context."
            ),
            provenance=build_provenance(
                clock=self.clock,
                source_reference_ids=trade.provenance.source_reference_ids,
                transformation_name="paper_trade_outcome_attribution",
                upstream_artifact_ids=[
                    outcome.trade_outcome_id,
                    trade.paper_trade_id,
                    state.paper_position_state_id,
                    proposal.portfolio_proposal_id,
                    position_idea.position_idea_id,
                    signal.signal_id,
                    *position_idea.research_artifact_ids,
                    *signal.feature_ids,
                    *proposal.review_decision_ids,
                    *trade.review_decision_ids,
                    *note_ids,
                ],
                notes=[],
            ),
            created_at=now,
            updated_at=now,
        )

    def _build_followups_for_outcome(
        self,
        *,
        trade: PaperTrade,
        state: PaperPositionState,
        outcome: TradeOutcome,
        instructions: list[str],
        now: datetime,
    ) -> list[ReviewFollowup]:
        followups: list[ReviewFollowup] = []
        for instruction in instructions:
            followups.append(
                ReviewFollowup(
                    review_followup_id=make_prefixed_id("rfup"),
                    paper_trade_id=trade.paper_trade_id,
                    paper_position_state_id=state.paper_position_state_id,
                    trade_outcome_id=outcome.trade_outcome_id,
                    status=ReviewFollowupStatus.OPEN,
                    instruction=instruction,
                    owner_id=None,
                    related_artifact_ids=[
                        trade.paper_trade_id,
                        state.paper_position_state_id,
                        outcome.trade_outcome_id,
                    ],
                    summary="Post-trade followup created from explicit outcome instructions.",
                    provenance=build_provenance(
                        clock=self.clock,
                        source_reference_ids=trade.provenance.source_reference_ids,
                        transformation_name="paper_trade_review_followup",
                        upstream_artifact_ids=[
                            trade.paper_trade_id,
                            state.paper_position_state_id,
                            outcome.trade_outcome_id,
                        ],
                        notes=[instruction],
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        return followups

    def _aggregate_daily_placeholder(
        self,
        *,
        open_states: list[PaperPositionState],
        reference_marks_by_symbol: dict[str, float],
    ) -> tuple[PnLPlaceholder | None, list[str]]:
        if not open_states:
            return None, []
        if not reference_marks_by_symbol:
            return None, ["reference_marks_missing_for_open_positions"]

        total_unrealized = 0.0
        incomplete_symbols: list[str] = []
        for state in open_states:
            mark = reference_marks_by_symbol.get(state.symbol)
            if mark is None or state.quantity is None or state.entry_reference_price_usd is None:
                incomplete_symbols.append(state.symbol)
                continue
            price_move = mark - state.entry_reference_price_usd
            signed_move = price_move if state.side is PositionSide.LONG else -price_move
            total_unrealized += state.quantity * signed_move
        if incomplete_symbols:
            return None, [f"incomplete_mark_coverage={','.join(sorted(set(incomplete_symbols)))}"]
        first_entry = open_states[0].entry_reference_price_usd
        first_mark = reference_marks_by_symbol.get(open_states[0].symbol)
        if first_entry is None or first_mark is None:
            return None, ["reference_marks_missing_for_open_positions"]
        return (
            PnLPlaceholder(
                entry_reference_price_usd=first_entry,
                current_or_exit_price_usd=first_mark,
                unrealized_pnl_usd=total_unrealized,
                realized_pnl_usd=None,
                complete=True,
                calculation_basis="aggregate_open_book_reference_marks",
                notes=["aggregate_placeholder_pnl"],
            ),
            [],
        )

    def _persist_trade_and_ledger_artifacts(
        self,
        *,
        store: LocalPaperLedgerArtifactStore,
        paper_trade: PaperTrade,
        paper_position_state: PaperPositionState,
        paper_ledger_entry: PaperLedgerEntry,
        position_lifecycle_event: PositionLifecycleEvent,
        review_followups: list[ReviewFollowup],
    ) -> list[ArtifactStorageLocation]:
        storage_locations = [
            store.persist_model(
                artifact_id=paper_trade.paper_trade_id,
                category="paper_trades",
                model=paper_trade,
                source_reference_ids=paper_trade.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=paper_position_state.paper_position_state_id,
                category="paper_position_states",
                model=paper_position_state,
                source_reference_ids=paper_position_state.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=paper_ledger_entry.paper_ledger_entry_id,
                category="paper_ledger_entries",
                model=paper_ledger_entry,
                source_reference_ids=paper_ledger_entry.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=position_lifecycle_event.position_lifecycle_event_id,
                category="position_lifecycle_events",
                model=position_lifecycle_event,
                source_reference_ids=position_lifecycle_event.provenance.source_reference_ids,
            ),
        ]
        for review_followup in review_followups:
            storage_locations.append(
                store.persist_model(
                    artifact_id=review_followup.review_followup_id,
                    category="review_followups",
                    model=review_followup,
                    source_reference_ids=review_followup.provenance.source_reference_ids,
                )
            )
        return storage_locations

    def _record_run_summary(
        self,
        *,
        workflow_name: str,
        workflow_run_id: str,
        requested_by: str,
        status: WorkflowStatus,
        started_at: datetime,
        completed_at: datetime,
        storage_locations: list[ArtifactStorageLocation],
        produced_artifact_ids: list[str],
        attention_reasons: list[str],
        notes: list[str],
        output_root: Path,
    ) -> RunSummary:
        response = MonitoringService(clock=self.clock).record_run_summary(
            RecordRunSummaryRequest(
                workflow_name=workflow_name,
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                requested_by=requested_by,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                storage_locations=storage_locations,
                produced_artifact_ids=produced_artifact_ids,
                attention_reasons=attention_reasons,
                notes=notes,
                outputs_expected=True,
            ),
            output_root=output_root,
        )
        return response.run_summary

    def _audit_service(self) -> AuditLoggingService:
        return AuditLoggingService(clock=self.clock)

    def _require_target(self, mapping: dict[str, T], target_id: str) -> T:
        target = mapping.get(target_id)
        if target is None:
            raise ValueError(f"Required artifact `{target_id}` was not found.")
        return target

    def _lifecycle_summary(
        self,
        event_type: PositionLifecycleEventType,
        symbol: str,
    ) -> str:
        return {
            PositionLifecycleEventType.SIMULATED_FILL_PLACEHOLDER: (
                f"Recorded placeholder simulated fill for {symbol}."
            ),
            PositionLifecycleEventType.MARK_UPDATED: f"Recorded mark update for {symbol}.",
            PositionLifecycleEventType.CLOSED: f"Recorded close event for {symbol}.",
            PositionLifecycleEventType.CANCELLED: f"Recorded cancellation event for {symbol}.",
            PositionLifecycleEventType.APPROVAL_ADMITTED: (
                f"Admitted approved trade for {symbol} into the paper ledger."
            ),
        }[event_type]

    def _ledger_summary(
        self,
        event_type: PositionLifecycleEventType,
        symbol: str,
    ) -> str:
        return {
            PositionLifecycleEventType.SIMULATED_FILL_PLACEHOLDER: (
                f"Ledger recorded placeholder simulated fill for {symbol}."
            ),
            PositionLifecycleEventType.MARK_UPDATED: f"Ledger recorded mark update for {symbol}.",
            PositionLifecycleEventType.CLOSED: f"Ledger recorded close event for {symbol}.",
            PositionLifecycleEventType.CANCELLED: f"Ledger recorded cancellation for {symbol}.",
            PositionLifecycleEventType.APPROVAL_ADMITTED: (
                f"Ledger recorded approval admission for {symbol}."
            ),
        }[event_type]
