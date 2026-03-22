from __future__ import annotations

from pydantic import Field

from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    PaperTrade,
    PaperTradeStatus,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionSide,
    StrictModel,
)
from libraries.utils import make_canonical_id, make_prefixed_id


class PaperTradeProposalRequest(StrictModel):
    """Request to translate an approved portfolio proposal into paper-trade candidates."""

    portfolio_proposal: PortfolioProposal = Field(
        description="Approved portfolio proposal to translate into paper trades."
    )
    assumed_reference_prices: dict[str, float] = Field(
        default_factory=dict,
        description="Optional symbol-to-price mapping used to materialize quantities.",
    )
    requested_by: str = Field(description="Requester identifier.")


class PaperTradeProposalResponse(StrictModel):
    """Response containing Day 7 paper-trade candidates."""

    trade_batch_id: str = Field(description="Identifier for the proposed paper-trade batch.")
    proposed_trades: list[PaperTrade] = Field(
        default_factory=list,
        description="Proposed paper trades.",
    )
    review_required: bool = Field(description="Whether trade-level approval is still required.")
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work or gating conditions.",
    )


class PaperExecutionService(BaseService):
    """Create human-reviewable paper trades without any live execution path."""

    capability_name = "paper_execution"
    capability_description = "Translates approved portfolio proposals into paper-only trade candidates."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PortfolioProposal"],
            produces=["PaperTrade"],
            api_routes=["GET /paper-trades/proposals"],
        )

    def propose_trades(self, request: PaperTradeProposalRequest) -> PaperTradeProposalResponse:
        """Create Day 7 paper-trade candidates from an approved proposal."""

        proposal = request.portfolio_proposal
        notes: list[str] = []
        if proposal.status is not PortfolioProposalStatus.APPROVED:
            notes.append(
                "Portfolio proposal is not approved, so zero paper-trade candidates were created."
            )
            notes.append(f"proposal_status={proposal.status.value}")
            return PaperTradeProposalResponse(
                trade_batch_id=make_prefixed_id("tradebatch"),
                proposed_trades=[],
                review_required=True,
                notes=notes,
            )
        if proposal.blocking_issues or any(check.blocking for check in proposal.risk_checks):
            notes.append("Proposal has blocking risk checks and cannot create paper trades.")
            return PaperTradeProposalResponse(
                trade_batch_id=make_prefixed_id("tradebatch"),
                proposed_trades=[],
                review_required=True,
                notes=notes,
            )

        now = self.clock.now()
        trades: list[PaperTrade] = []
        for idea in proposal.position_ideas:
            if idea.side is PositionSide.FLAT:
                continue
            reference_price = request.assumed_reference_prices.get(idea.symbol)
            notional_usd = proposal.target_nav_usd * abs(idea.proposed_weight_bps) / 10_000.0
            quantity = (
                notional_usd / reference_price
                if reference_price is not None and reference_price > 0.0
                else None
            )
            trades.append(
                PaperTrade(
                    paper_trade_id=make_canonical_id(
                        "trade",
                        proposal.portfolio_proposal_id,
                        idea.position_idea_id,
                    ),
                    portfolio_proposal_id=proposal.portfolio_proposal_id,
                    position_idea_id=idea.position_idea_id,
                    symbol=idea.symbol,
                    side=idea.side,
                    execution_mode="paper_only",
                    quantity=quantity,
                    notional_usd=notional_usd,
                    assumed_reference_price_usd=reference_price,
                    time_in_force="day",
                    status=PaperTradeStatus.PROPOSED,
                    submitted_at=now,
                    approved_at=None,
                    simulated_fill_at=None,
                    requested_by=request.requested_by,
                    approved_by=None,
                    review_decision_ids=[],
                    execution_notes=[
                        "Simulated only. No live routing.",
                        "Trade candidate requires separate human review.",
                        f"proposal_status={proposal.status.value}",
                    ],
                    slippage_bps_estimate=5.0,
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day7_paper_trade_translation",
                        source_reference_ids=idea.provenance.source_reference_ids,
                        upstream_artifact_ids=[
                            proposal.portfolio_proposal_id,
                            idea.position_idea_id,
                            idea.signal_id,
                        ],
                        notes=[
                            "execution_mode=paper_only",
                            (
                                f"reference_price_used={reference_price:.4f}"
                                if reference_price is not None
                                else "reference_price_used=none"
                            ),
                        ],
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        if not trades:
            notes.append("No directional position ideas were eligible for paper-trade creation.")
        return PaperTradeProposalResponse(
            trade_batch_id=make_prefixed_id("tradebatch"),
            proposed_trades=trades,
            review_required=True,
            notes=notes,
        )
