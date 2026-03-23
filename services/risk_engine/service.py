from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArbitrationDecision,
    ConstraintResult,
    ConstraintSet,
    ConstructionDecision,
    EvidenceAssessment,
    PortfolioAttribution,
    PortfolioConstraint,
    PortfolioProposal,
    PortfolioSelectionSummary,
    PositionIdea,
    PositionSizingRationale,
    RiskCheck,
    SelectionConflict,
    Signal,
    SignalBundle,
    SignalConflict,
    StressTestResult,
    StressTestRun,
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
    constraint_set: ConstraintSet | None = Field(
        default=None,
        description="Optional portfolio-construction constraint set for proposal explainability.",
    )
    constraint_results: list[ConstraintResult] = Field(
        default_factory=list,
        description="Optional portfolio-construction constraint results for proposal explainability.",
    )
    position_sizing_rationales: list[PositionSizingRationale] = Field(
        default_factory=list,
        description="Optional position-sizing rationales for included positions.",
    )
    construction_decisions: list[ConstructionDecision] = Field(
        default_factory=list,
        description="Optional construction decisions explaining included and rejected candidates.",
    )
    selection_conflicts: list[SelectionConflict] = Field(
        default_factory=list,
        description="Optional construction conflicts kept visible during risk review.",
    )
    portfolio_selection_summary: PortfolioSelectionSummary | None = Field(
        default=None,
        description="Optional parent portfolio-construction summary.",
    )
    portfolio_attribution: PortfolioAttribution | None = Field(
        default=None,
        description="Optional portfolio-attribution artifact for explainability and fragility review.",
    )
    stress_test_run: StressTestRun | None = Field(
        default=None,
        description="Optional stress-test run artifact for proposal fragility review.",
    )
    stress_test_results: list[StressTestResult] = Field(
        default_factory=list,
        description="Optional structured stress-test results for proposal review.",
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
            constraint_set=request.constraint_set,
            constraint_results=request.constraint_results,
            position_sizing_rationales=request.position_sizing_rationales,
            construction_decisions=request.construction_decisions,
            selection_conflicts=request.selection_conflicts,
            portfolio_selection_summary=request.portfolio_selection_summary,
            portfolio_attribution=request.portfolio_attribution,
            stress_test_run=request.stress_test_run,
            stress_test_results=request.stress_test_results,
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
