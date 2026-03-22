from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArbitrationDecision,
    EvidenceAssessment,
    PortfolioConstraint,
    PortfolioProposal,
    PositionIdea,
    RiskCheck,
    Signal,
    SignalBundle,
    SignalConflict,
    StrictModel,
)
from libraries.utils import make_prefixed_id
from services.risk_engine.rules import evaluate_portfolio_risk


class RiskEvaluationRequest(StrictModel):
    """Request to run explicit Day 7 risk checks on a portfolio proposal."""

    position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Position ideas to evaluate if no portfolio proposal is supplied.",
    )
    portfolio_proposal: PortfolioProposal | None = Field(
        default=None,
        description="Portfolio proposal to evaluate when available.",
    )
    constraints: list[PortfolioConstraint] = Field(
        default_factory=list,
        description="Explicit constraints applicable to the current proposal.",
    )
    signals_by_id: dict[str, Signal] = Field(
        default_factory=dict,
        description="Signals keyed by signal ID for provenance and maturity checks.",
    )
    evidence_assessments_by_id: dict[str, EvidenceAssessment] = Field(
        default_factory=dict,
        description="Evidence assessments keyed by identifier for support-grade checks.",
    )
    signal_bundle: SignalBundle | None = Field(
        default=None,
        description="Optional signal bundle used to source the portfolio input.",
    )
    arbitration_decision: ArbitrationDecision | None = Field(
        default=None,
        description="Optional arbitration decision used to source the portfolio input.",
    )
    signal_conflicts: list[SignalConflict] = Field(
        default_factory=list,
        description="Optional signal conflicts that should remain visible in risk review.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RiskEvaluationResponse(StrictModel):
    """Response returned after explicit risk checks are evaluated."""

    evaluation_id: str = Field(description="Risk evaluation batch identifier.")
    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Explicit risk checks produced by the Day 7 rule set.",
    )
    risk_check_ids: list[str] = Field(
        default_factory=list,
        description="Generated risk check identifiers.",
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Blocking issues requiring human review or revision.",
    )
    evaluated_at: datetime = Field(description="UTC timestamp when evaluation completed.")


class RiskEngineService(BaseService):
    """Evaluate explicit risk and compliance guardrails before paper-trade review."""

    capability_name = "risk_engine"
    capability_description = "Applies inspectable Day 7 risk and policy checks to proposals."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PositionIdea", "PortfolioProposal", "Signal", "EvidenceAssessment"],
            produces=["RiskCheck"],
            api_routes=[],
        )

    def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationResponse:
        """Run the deterministic Day 7 risk rules and return full risk checks."""

        evaluation_id = make_prefixed_id("riskeval")
        result = evaluate_portfolio_risk(
            position_ideas=request.position_ideas,
            portfolio_proposal=request.portfolio_proposal,
            constraints=request.constraints
            or (request.portfolio_proposal.constraints if request.portfolio_proposal else []),
            signals_by_id=request.signals_by_id,
            evidence_assessments_by_id=request.evidence_assessments_by_id,
            signal_bundle=request.signal_bundle,
            arbitration_decision=request.arbitration_decision,
            signal_conflicts=request.signal_conflicts,
            clock=self.clock,
            workflow_run_id=evaluation_id,
        )
        return RiskEvaluationResponse(
            evaluation_id=evaluation_id,
            risk_checks=result.risk_checks,
            risk_check_ids=[risk_check.risk_check_id for risk_check in result.risk_checks],
            blocking_issues=result.blocking_issues,
            evaluated_at=self.clock.now(),
        )
