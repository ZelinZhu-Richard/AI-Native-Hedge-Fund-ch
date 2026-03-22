from __future__ import annotations

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    ArbitrationDecision,
    ConstraintType,
    EvidenceAssessment,
    EvidenceGrade,
    PortfolioConstraint,
    PortfolioProposal,
    PositionIdea,
    RiskCheck,
    RiskCheckStatus,
    Severity,
    Signal,
    SignalBundle,
    SignalConflict,
    StrictModel,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id


class RiskEvaluationResult(StrictModel):
    """Structured output of the deterministic Day 7 risk review rules."""

    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Explicit risk checks emitted by the Day 7 rule set.",
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Blocking issues derived from blocking risk checks.",
    )


def evaluate_portfolio_risk(
    *,
    position_ideas: list[PositionIdea],
    portfolio_proposal: PortfolioProposal | None,
    constraints: list[PortfolioConstraint],
    signals_by_id: dict[str, Signal],
    evidence_assessments_by_id: dict[str, EvidenceAssessment],
    signal_bundle: SignalBundle | None,
    arbitration_decision: ArbitrationDecision | None,
    signal_conflicts: list[SignalConflict],
    clock: Clock,
    workflow_run_id: str,
) -> RiskEvaluationResult:
    """Evaluate the explicit Day 7 risk rules for a proposal and its positions."""

    risk_checks: list[RiskCheck] = []
    if signal_bundle is None or arbitration_decision is None:
        risk_checks.append(
            _build_risk_check(
                subject_type="portfolio_proposal",
                subject_id=(
                    portfolio_proposal.portfolio_proposal_id
                    if portfolio_proposal is not None
                    else "portfolio_proposal_pending"
                ),
                rule_name="signal_arbitration_missing",
                status=RiskCheckStatus.WARN,
                severity=Severity.MEDIUM,
                blocking=False,
                message=(
                    "Signal arbitration context is missing. Portfolio review is using raw signals directly."
                ),
                clock=clock,
                workflow_run_id=workflow_run_id,
                upstream_artifact_ids=[
                    *( [portfolio_proposal.portfolio_proposal_id] if portfolio_proposal is not None else [] ),
                    *signals_by_id.keys(),
                ],
                source_reference_ids=[
                    source_reference_id
                    for signal in signals_by_id.values()
                    for source_reference_id in signal.provenance.source_reference_ids
                ],
            )
        )
    elif signal_conflicts:
        risk_checks.append(
            _build_risk_check(
                subject_type="portfolio_proposal",
                subject_id=(
                    portfolio_proposal.portfolio_proposal_id
                    if portfolio_proposal is not None
                    else "portfolio_proposal_pending"
                ),
                rule_name="signal_arbitration_conflicts_present",
                status=RiskCheckStatus.WARN,
                severity=Severity.MEDIUM,
                blocking=False,
                message="Signal arbitration observed conflicts that should remain visible in review.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                upstream_artifact_ids=[
                    *( [portfolio_proposal.portfolio_proposal_id] if portfolio_proposal is not None else [] ),
                    signal_bundle.signal_bundle_id,
                    arbitration_decision.arbitration_decision_id,
                    *[conflict.signal_conflict_id for conflict in signal_conflicts],
                ],
                source_reference_ids=[
                    source_reference_id
                    for signal in signals_by_id.values()
                    for source_reference_id in signal.provenance.source_reference_ids
                ],
            )
        )
    for idea in position_ideas:
        signal = signals_by_id.get(idea.signal_id)
        evidence_assessment = _find_evidence_assessment(
            idea=idea,
            evidence_assessments_by_id=evidence_assessments_by_id,
        )

        if not idea.signal_id or not idea.supporting_evidence_link_ids or not idea.selection_reason:
            risk_checks.append(
                _build_risk_check(
                    subject_type="position_idea",
                    subject_id=idea.position_idea_id,
                    rule_name="position_input_completeness",
                    status=RiskCheckStatus.FAIL,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Position idea is missing signal linkage, evidence linkage, or rationale.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    upstream_artifact_ids=[idea.position_idea_id, idea.signal_id],
                    source_reference_ids=idea.provenance.source_reference_ids,
                )
            )
        single_name_constraint = _constraint_by_type(
            constraints=constraints,
            constraint_type=ConstraintType.SINGLE_NAME,
        )
        if (
            single_name_constraint is not None
            and single_name_constraint.hard_limit is not None
            and idea.proposed_weight_bps > single_name_constraint.hard_limit
        ):
            risk_checks.append(
                _build_risk_check(
                    subject_type="position_idea",
                    subject_id=idea.position_idea_id,
                    portfolio_constraint_id=single_name_constraint.portfolio_constraint_id,
                    rule_name="single_name_weight_limit",
                    status=RiskCheckStatus.FAIL,
                    severity=Severity.HIGH,
                    blocking=True,
                    observed_value=float(idea.proposed_weight_bps),
                    limit_value=float(single_name_constraint.hard_limit),
                    unit=single_name_constraint.unit,
                    message=(
                        f"Position weight {idea.proposed_weight_bps} bps exceeds the "
                        f"single-name limit of {single_name_constraint.hard_limit:.0f} bps."
                    ),
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    upstream_artifact_ids=[idea.position_idea_id, idea.signal_id],
                    source_reference_ids=idea.provenance.source_reference_ids,
                )
            )
        if signal is None:
            risk_checks.append(
                _build_risk_check(
                    subject_type="position_idea",
                    subject_id=idea.position_idea_id,
                    rule_name="missing_signal",
                    status=RiskCheckStatus.FAIL,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Referenced signal was not found for the position idea.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    upstream_artifact_ids=[idea.position_idea_id, idea.signal_id],
                    source_reference_ids=idea.provenance.source_reference_ids,
                )
            )
        else:
            if signal.status.value == "candidate" or signal.validation_status.value != "validated":
                risk_checks.append(
                    _build_risk_check(
                        subject_type="position_idea",
                        subject_id=idea.position_idea_id,
                        rule_name="signal_review_maturity",
                        status=RiskCheckStatus.WARN,
                        severity=Severity.MEDIUM,
                        blocking=False,
                        message=(
                            "Position idea relies on a candidate or unvalidated signal and "
                            "must remain human-review-gated."
                        ),
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                        upstream_artifact_ids=[idea.position_idea_id, signal.signal_id],
                        source_reference_ids=signal.provenance.source_reference_ids,
                    )
                )
        if evidence_assessment is not None:
            if evidence_assessment.grade in {EvidenceGrade.WEAK, EvidenceGrade.INSUFFICIENT}:
                risk_checks.append(
                    _build_risk_check(
                        subject_type="position_idea",
                        subject_id=idea.position_idea_id,
                        rule_name="weak_research_support",
                        status=RiskCheckStatus.FAIL,
                        severity=Severity.HIGH,
                        blocking=True,
                        message=(
                            f"Evidence assessment grade `{evidence_assessment.grade.value}` is "
                            "too weak for portfolio inclusion."
                        ),
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                        upstream_artifact_ids=[
                            idea.position_idea_id,
                            evidence_assessment.evidence_assessment_id,
                        ],
                        source_reference_ids=evidence_assessment.provenance.source_reference_ids,
                    )
                )
            elif evidence_assessment.grade is EvidenceGrade.MODERATE:
                risk_checks.append(
                    _build_risk_check(
                        subject_type="position_idea",
                        subject_id=idea.position_idea_id,
                        rule_name="moderate_research_support",
                        status=RiskCheckStatus.WARN,
                        severity=Severity.MEDIUM,
                        blocking=False,
                        message=(
                            "Evidence support is only moderate. Position idea should remain "
                            "provisional until further validation."
                        ),
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                        upstream_artifact_ids=[
                            idea.position_idea_id,
                            evidence_assessment.evidence_assessment_id,
                        ],
                        source_reference_ids=evidence_assessment.provenance.source_reference_ids,
                    )
                )

    if portfolio_proposal is not None:
        gross_constraint = _constraint_by_type(
            constraints=constraints,
            constraint_type=ConstraintType.GROSS_EXPOSURE,
        )
        if (
            gross_constraint is not None
            and gross_constraint.hard_limit is not None
            and portfolio_proposal.exposure_summary.gross_exposure_bps > gross_constraint.hard_limit
        ):
            risk_checks.append(
                _build_risk_check(
                    subject_type="portfolio_proposal",
                    subject_id=portfolio_proposal.portfolio_proposal_id,
                    portfolio_constraint_id=gross_constraint.portfolio_constraint_id,
                    rule_name="gross_exposure_limit",
                    status=RiskCheckStatus.FAIL,
                    severity=Severity.HIGH,
                    blocking=True,
                    observed_value=float(portfolio_proposal.exposure_summary.gross_exposure_bps),
                    limit_value=float(gross_constraint.hard_limit),
                    unit=gross_constraint.unit,
                    message="Portfolio proposal exceeds the gross exposure limit.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    upstream_artifact_ids=[portfolio_proposal.portfolio_proposal_id],
                    source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
                )
            )
        net_constraint = _constraint_by_type(
            constraints=constraints,
            constraint_type=ConstraintType.NET_EXPOSURE,
        )
        if (
            net_constraint is not None
            and net_constraint.hard_limit is not None
            and abs(portfolio_proposal.exposure_summary.net_exposure_bps) > net_constraint.hard_limit
        ):
            risk_checks.append(
                _build_risk_check(
                    subject_type="portfolio_proposal",
                    subject_id=portfolio_proposal.portfolio_proposal_id,
                    portfolio_constraint_id=net_constraint.portfolio_constraint_id,
                    rule_name="net_exposure_limit",
                    status=RiskCheckStatus.FAIL,
                    severity=Severity.HIGH,
                    blocking=True,
                    observed_value=float(abs(portfolio_proposal.exposure_summary.net_exposure_bps)),
                    limit_value=float(net_constraint.hard_limit),
                    unit=net_constraint.unit,
                    message="Portfolio proposal exceeds the absolute net exposure limit.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    upstream_artifact_ids=[portfolio_proposal.portfolio_proposal_id],
                    source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
                )
            )
        turnover_constraint = _constraint_by_type(
            constraints=constraints,
            constraint_type=ConstraintType.TURNOVER,
        )
        if (
            turnover_constraint is not None
            and turnover_constraint.hard_limit is not None
            and portfolio_proposal.exposure_summary.turnover_bps_assumption
            > turnover_constraint.hard_limit
        ):
            risk_checks.append(
                _build_risk_check(
                    subject_type="portfolio_proposal",
                    subject_id=portfolio_proposal.portfolio_proposal_id,
                    portfolio_constraint_id=turnover_constraint.portfolio_constraint_id,
                    rule_name="flat_start_turnover_limit",
                    status=RiskCheckStatus.FAIL,
                    severity=Severity.MEDIUM,
                    blocking=True,
                    observed_value=float(portfolio_proposal.exposure_summary.turnover_bps_assumption),
                    limit_value=float(turnover_constraint.hard_limit),
                    unit=turnover_constraint.unit,
                    message="Flat-start turnover assumption exceeds the turnover limit.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    upstream_artifact_ids=[portfolio_proposal.portfolio_proposal_id],
                    source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
                )
            )

    blocking_issues = [risk_check.message for risk_check in risk_checks if risk_check.blocking]
    return RiskEvaluationResult(risk_checks=risk_checks, blocking_issues=blocking_issues)


def _constraint_by_type(
    *,
    constraints: list[PortfolioConstraint],
    constraint_type: ConstraintType,
) -> PortfolioConstraint | None:
    """Return the active constraint for one type when available."""

    for constraint in constraints:
        if constraint.active and constraint.constraint_type is constraint_type:
            return constraint
    return None


def _find_evidence_assessment(
    *,
    idea: PositionIdea,
    evidence_assessments_by_id: dict[str, EvidenceAssessment],
) -> EvidenceAssessment | None:
    """Resolve the evidence assessment attached to one position idea when present."""

    for artifact_id in idea.research_artifact_ids:
        if artifact_id in evidence_assessments_by_id:
            return evidence_assessments_by_id[artifact_id]
    return None


def _build_risk_check(
    *,
    subject_type: str,
    subject_id: str,
    rule_name: str,
    status: RiskCheckStatus,
    severity: Severity,
    blocking: bool,
    message: str,
    clock: Clock,
    workflow_run_id: str,
    upstream_artifact_ids: list[str],
    source_reference_ids: list[str],
    portfolio_constraint_id: str | None = None,
    observed_value: float | None = None,
    limit_value: float | None = None,
    unit: str | None = None,
) -> RiskCheck:
    """Build one explicit Day 7 risk check."""

    now = clock.now()
    return RiskCheck(
        risk_check_id=make_canonical_id("risk", subject_id, rule_name),
        subject_type=subject_type,
        subject_id=subject_id,
        portfolio_constraint_id=portfolio_constraint_id,
        rule_name=rule_name,
        status=status,
        severity=severity,
        blocking=blocking,
        observed_value=observed_value,
        limit_value=limit_value,
        unit=unit,
        message=message,
        checked_at=now,
        reviewer_notes=[],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day7_risk_review",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=upstream_artifact_ids,
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )
