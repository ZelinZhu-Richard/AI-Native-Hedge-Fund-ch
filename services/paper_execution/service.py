from __future__ import annotations

from pydantic import Field

from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    PaperTrade,
    PaperTradeStatus,
    PositionIdea,
    PositionSide,
    StrictModel,
)
from libraries.utils import make_prefixed_id


class PaperTradeProposalRequest(StrictModel):
    """Request to translate approved portfolio views into simulated trades."""

    portfolio_proposal_id: str = Field(description="Owning portfolio proposal identifier.")
    position_ideas: list[PositionIdea] = Field(description="Approved position ideas to simulate.")
    requested_by: str = Field(description="Requester identifier.")


class PaperTradeProposalResponse(StrictModel):
    """Response containing paper trade proposals."""

    trade_batch_id: str = Field(description="Identifier for the proposed trade batch.")
    proposed_trades: list[PaperTrade] = Field(
        default_factory=list, description="Proposed paper trades."
    )
    review_required: bool = Field(description="Whether paper trade approval is still required.")


class PaperExecutionService(BaseService):
    """Create human-reviewable simulated trades without touching real brokers."""

    capability_name = "paper_execution"
    capability_description = "Translates approved proposals into reviewable paper trades."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PortfolioProposal", "PositionIdea"],
            produces=["PaperTrade"],
            api_routes=["GET /paper-trades/proposals"],
        )

    def propose_trades(self, request: PaperTradeProposalRequest) -> PaperTradeProposalResponse:
        """Create placeholder paper trade proposals from position ideas."""

        now = self.clock.now()
        trades = [
            PaperTrade(
                paper_trade_id=make_prefixed_id("trade"),
                portfolio_proposal_id=request.portfolio_proposal_id,
                position_idea_id=idea.position_idea_id,
                symbol=idea.symbol,
                side=idea.side,
                quantity=100.0,
                notional_usd=float(abs(idea.proposed_weight_bps) * 10),
                time_in_force="day",
                status=PaperTradeStatus.PROPOSED,
                submitted_at=now,
                requested_by=request.requested_by,
                execution_notes=["Simulated only. No live routing."],
                slippage_bps_estimate=5.0,
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="paper_trade_stub",
                    upstream_artifact_ids=[idea.position_idea_id, request.portfolio_proposal_id],
                ),
                created_at=now,
                updated_at=now,
            )
            for idea in request.position_ideas
            if idea.side != PositionSide.FLAT
        ]
        return PaperTradeProposalResponse(
            trade_batch_id=make_prefixed_id("tradebatch"),
            proposed_trades=trades,
            review_required=True,
        )
