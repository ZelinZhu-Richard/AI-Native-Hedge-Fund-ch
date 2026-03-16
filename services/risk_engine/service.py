from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import PortfolioProposal, PositionIdea, StrictModel
from libraries.utils import make_prefixed_id


class RiskEvaluationRequest(StrictModel):
    """Request to run risk checks on position ideas or a portfolio proposal."""

    position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Position ideas to evaluate if no portfolio proposal is supplied.",
    )
    portfolio_proposal: PortfolioProposal | None = Field(
        default=None,
        description="Portfolio proposal to evaluate when available.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RiskEvaluationResponse(StrictModel):
    """Response returned after risk checks are evaluated."""

    evaluation_id: str = Field(description="Risk evaluation batch identifier.")
    risk_check_ids: list[str] = Field(
        default_factory=list, description="Generated risk check identifiers."
    )
    blocking_issues: list[str] = Field(
        default_factory=list, description="Blocking issues requiring review."
    )
    evaluated_at: datetime = Field(description="UTC timestamp when evaluation completed.")


class RiskEngineService(BaseService):
    """Evaluate risk and compliance guardrails before simulation or approval."""

    capability_name = "risk_engine"
    capability_description = "Applies risk and policy checks to ideas, proposals, and paper trades."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PositionIdea", "PortfolioProposal"],
            produces=["RiskCheck"],
            api_routes=[],
        )

    def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationResponse:
        """Return placeholder risk evaluation results."""

        risk_check_count = len(request.position_ideas)
        if risk_check_count == 0 and request.portfolio_proposal is not None:
            risk_check_count = len(request.portfolio_proposal.position_ideas)
        if risk_check_count == 0:
            risk_check_count = 1
        return RiskEvaluationResponse(
            evaluation_id=make_prefixed_id("riskeval"),
            risk_check_ids=[make_prefixed_id("risk") for _ in range(risk_check_count)],
            blocking_issues=[],
            evaluated_at=self.clock.now(),
        )
