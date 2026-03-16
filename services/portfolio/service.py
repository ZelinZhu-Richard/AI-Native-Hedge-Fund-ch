from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    PortfolioConstraint,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    StrictModel,
)
from libraries.utils import make_prefixed_id


class PortfolioConstructionRequest(StrictModel):
    """Request to assemble a paper portfolio proposal."""

    name: str = Field(description="Proposed portfolio name.")
    as_of_time: datetime = Field(description="UTC time the proposal should respect.")
    position_ideas: list[PositionIdea] = Field(description="Candidate position ideas.")
    constraints: list[PortfolioConstraint] = Field(
        default_factory=list, description="Constraints to apply."
    )
    requested_by: str = Field(description="Requester identifier.")


class PortfolioConstructionResponse(StrictModel):
    """Response returned after a portfolio proposal is assembled."""

    proposal: PortfolioProposal = Field(description="Constructed paper portfolio proposal.")


class PortfolioConstructionService(BaseService):
    """Assemble reviewed position ideas into a constrained paper portfolio proposal."""

    capability_name = "portfolio"
    capability_description = "Constructs paper portfolio proposals from reviewed ideas."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PositionIdea", "PortfolioConstraint"],
            produces=["PortfolioProposal"],
            api_routes=["GET /portfolio-proposals"],
        )

    def construct(self, request: PortfolioConstructionRequest) -> PortfolioConstructionResponse:
        """Build a placeholder portfolio proposal while preserving review requirements."""

        now = self.clock.now()
        gross_exposure_bps = sum(abs(idea.proposed_weight_bps) for idea in request.position_ideas)
        net_exposure_bps = sum(
            0
            if idea.side.value == "flat"
            else (
                idea.proposed_weight_bps if idea.side.value == "long" else -idea.proposed_weight_bps
            )
            for idea in request.position_ideas
        )
        proposal = PortfolioProposal(
            portfolio_proposal_id=make_prefixed_id("proposal"),
            name=request.name,
            as_of_time=request.as_of_time,
            generated_at=now,
            position_ideas=request.position_ideas,
            constraints=request.constraints,
            risk_checks=[],
            gross_exposure_bps=gross_exposure_bps,
            net_exposure_bps=net_exposure_bps,
            cash_buffer_bps=max(0, 10_000 - gross_exposure_bps),
            review_required=True,
            status=PortfolioProposalStatus.DRAFT,
            summary="Day 1 placeholder proposal assembled from reviewed position ideas.",
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="portfolio_construction_stub",
                upstream_artifact_ids=[idea.position_idea_id for idea in request.position_ideas],
            ),
            created_at=now,
            updated_at=now,
        )
        return PortfolioConstructionResponse(proposal=proposal)
