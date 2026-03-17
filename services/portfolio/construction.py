from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    ConstraintType,
    DerivedArtifactValidationStatus,
    EvidenceAssessment,
    PortfolioConstraint,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    ResearchBrief,
    ResearchStance,
    Signal,
    SignalStatus,
    StrictModel,
    SupportingEvidenceLink,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.portfolio.loaders import LoadedPortfolioInputs


class PositionIdeaBuildResult(StrictModel):
    """Structured output of signal-to-position mapping."""

    position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Reviewable position ideas materialized from eligible signals.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped or constrained mappings.",
    )


def default_portfolio_constraints(*, clock: Clock, workflow_run_id: str) -> list[PortfolioConstraint]:
    """Build the default Day 7 hard constraints for local portfolio workflows."""

    now = clock.now()
    constraints = [
        (
            ConstraintType.SINGLE_NAME,
            "single_name",
            500.0,
            "bps",
            "No single position may exceed 500 bps of target NAV.",
        ),
        (
            ConstraintType.GROSS_EXPOSURE,
            "portfolio",
            1500.0,
            "bps",
            "Gross exposure must remain at or below 1500 bps.",
        ),
        (
            ConstraintType.NET_EXPOSURE,
            "portfolio",
            1000.0,
            "bps",
            "Absolute net exposure must remain at or below 1000 bps.",
        ),
        (
            ConstraintType.TURNOVER,
            "portfolio",
            1500.0,
            "bps",
            "Flat-start turnover assumption must remain at or below 1500 bps.",
        ),
    ]
    return [
        PortfolioConstraint(
            portfolio_constraint_id=make_canonical_id(
                "constraint",
                constraint_type.value,
                scope,
                str(hard_limit),
            ),
            constraint_type=constraint_type,
            scope=scope,
            hard_limit=hard_limit,
            soft_limit=None,
            unit=unit,
            description=description,
            active=True,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day7_default_portfolio_constraints",
                workflow_run_id=workflow_run_id,
                notes=[f"constraint_type={constraint_type.value}"],
            ),
            created_at=now,
            updated_at=now,
        )
        for constraint_type, scope, hard_limit, unit, description in constraints
    ]


def build_position_ideas(
    *,
    inputs: LoadedPortfolioInputs,
    as_of_time: datetime,
    clock: Clock,
    workflow_run_id: str,
) -> PositionIdeaBuildResult:
    """Map eligible signals into reviewable Day 7 position ideas."""

    notes: list[str] = []
    company_ticker = inputs.company.ticker if inputs.company is not None else None
    if not company_ticker:
        notes.append(
            "No ticker was found in normalized company metadata; no position ideas were created."
        )
        return PositionIdeaBuildResult(notes=notes)

    position_ideas: list[PositionIdea] = []
    for signal in inputs.signals:
        if signal.status not in {SignalStatus.CANDIDATE, SignalStatus.APPROVED}:
            notes.append(
                f"Skipped signal `{signal.signal_id}` because status `{signal.status.value}` is not "
                "eligible for Day 7 proposals."
            )
            continue
        if signal.stance in {ResearchStance.MIXED, ResearchStance.MONITOR}:
            notes.append(
                f"Skipped signal `{signal.signal_id}` because stance `{signal.stance.value}` "
                "does not express a directional portfolio view."
            )
            continue

        side = (
            PositionSide.LONG
            if signal.stance is ResearchStance.POSITIVE
            else PositionSide.SHORT
        )
        proposed_weight_bps = (
            500
            if signal.status is SignalStatus.APPROVED
            and signal.validation_status is DerivedArtifactValidationStatus.VALIDATED
            else 300
        )
        research_brief = _find_research_brief(inputs=inputs, signal=signal)
        evidence_assessment = _find_evidence_assessment(inputs=inputs, signal=signal)
        evidence_links = (
            research_brief.supporting_evidence_links
            if research_brief is not None
            else _supporting_links_from_hypothesis(inputs=inputs, signal=signal)
        )
        if not evidence_links:
            notes.append(
                f"Skipped signal `{signal.signal_id}` because no exact supporting evidence links "
                "could be resolved from research artifacts."
            )
            continue

        evidence_span_ids = sorted({link.evidence_span_id for link in evidence_links})
        supporting_evidence_link_ids = sorted(
            {link.supporting_evidence_link_id for link in evidence_links}
        )
        research_artifact_ids = sorted(
            {
                signal.hypothesis_id,
                *signal.lineage.research_artifact_ids,
                *([research_brief.research_brief_id] if research_brief is not None else []),
                *(
                    [evidence_assessment.evidence_assessment_id]
                    if evidence_assessment is not None
                    else []
                ),
            }
        )
        target_horizon = _target_horizon(inputs=inputs, signal=signal)
        now = clock.now()
        position_idea_id = make_canonical_id(
            "idea",
            signal.signal_id,
            signal.stance.value,
            as_of_time.isoformat(),
        )
        position_ideas.append(
            PositionIdea(
                position_idea_id=position_idea_id,
                company_id=inputs.company_id,
                signal_id=signal.signal_id,
                symbol=company_ticker,
                instrument_type="equity",
                side=side,
                thesis_summary=signal.thesis_summary,
                selection_reason=(
                    f"Selected from signal `{signal.signal_family}` with score "
                    f"{signal.primary_score:.2f} and stance `{signal.stance.value}`."
                ),
                entry_conditions=[
                    "Human review completed.",
                    "Blocking portfolio risk checks resolved.",
                ],
                exit_conditions=[
                    "Signal stance is withdrawn or flips direction.",
                    "New evidence invalidates the core hypothesis.",
                ],
                target_horizon=target_horizon,
                proposed_weight_bps=proposed_weight_bps,
                max_weight_bps=500,
                evidence_span_ids=evidence_span_ids,
                supporting_evidence_link_ids=supporting_evidence_link_ids,
                research_artifact_ids=research_artifact_ids,
                review_decision_ids=[],
                status=PositionIdeaStatus.PENDING_REVIEW,
                confidence=signal.confidence,
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day7_signal_to_position_mapping",
                    source_reference_ids=signal.provenance.source_reference_ids,
                    upstream_artifact_ids=[signal.signal_id, *research_artifact_ids],
                    workflow_run_id=workflow_run_id,
                    notes=[
                        f"signal_status={signal.status.value}",
                        f"signal_validation_status={signal.validation_status.value}",
                    ],
                ),
                created_at=now,
                updated_at=now,
            )
        )
    return PositionIdeaBuildResult(position_ideas=position_ideas, notes=notes)


def build_exposure_summary(
    *,
    position_ideas: list[PositionIdea],
    clock: Clock,
    workflow_run_id: str,
    summary_key: str,
) -> PortfolioExposureSummary:
    """Compute an explicit exposure summary from position ideas."""

    now = clock.now()
    long_exposure_bps = sum(
        idea.proposed_weight_bps for idea in position_ideas if idea.side is PositionSide.LONG
    )
    short_exposure_bps = sum(
        idea.proposed_weight_bps for idea in position_ideas if idea.side is PositionSide.SHORT
    )
    gross_exposure_bps = long_exposure_bps + short_exposure_bps
    net_exposure_bps = long_exposure_bps - short_exposure_bps
    turnover_bps_assumption = gross_exposure_bps
    cash_buffer_bps = max(0, 10_000 - gross_exposure_bps)
    return PortfolioExposureSummary(
        portfolio_exposure_summary_id=make_canonical_id("pexpo", summary_key),
        gross_exposure_bps=gross_exposure_bps,
        net_exposure_bps=net_exposure_bps,
        long_exposure_bps=long_exposure_bps,
        short_exposure_bps=short_exposure_bps,
        cash_buffer_bps=cash_buffer_bps,
        position_count=len(position_ideas),
        turnover_bps_assumption=turnover_bps_assumption,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day7_portfolio_exposure_summary",
            upstream_artifact_ids=[idea.position_idea_id for idea in position_ideas],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_portfolio_proposal(
    *,
    company_id: str,
    name: str,
    as_of_time: datetime,
    generated_at: datetime,
    target_nav_usd: float,
    position_ideas: list[PositionIdea],
    constraints: list[PortfolioConstraint],
    exposure_summary: PortfolioExposureSummary,
    clock: Clock,
    workflow_run_id: str,
) -> PortfolioProposal:
    """Build one Day 7 reviewable portfolio proposal from position ideas."""

    proposal_id = make_canonical_id("proposal", company_id, as_of_time.isoformat(), name)
    return PortfolioProposal(
        portfolio_proposal_id=proposal_id,
        name=name,
        as_of_time=as_of_time,
        generated_at=generated_at,
        target_nav_usd=target_nav_usd,
        position_ideas=position_ideas,
        constraints=constraints,
        risk_checks=[],
        exposure_summary=exposure_summary,
        blocking_issues=[],
        review_decision_ids=[],
        review_required=True,
        status=PortfolioProposalStatus.PENDING_REVIEW,
        summary=(
            f"{len(position_ideas)} position ideas, gross {exposure_summary.gross_exposure_bps} bps, "
            f"net {exposure_summary.net_exposure_bps} bps."
        ),
        provenance=build_provenance(
            clock=clock,
            transformation_name="day7_portfolio_proposal_assembly",
            upstream_artifact_ids=[idea.position_idea_id for idea in position_ideas],
            workflow_run_id=workflow_run_id,
        ),
        created_at=generated_at,
        updated_at=generated_at,
    )


def _find_research_brief(
    *,
    inputs: LoadedPortfolioInputs,
    signal: Signal,
) -> ResearchBrief | None:
    """Resolve the primary research brief referenced by a signal lineage when available."""

    for artifact_id in signal.lineage.research_artifact_ids:
        if artifact_id in inputs.research_briefs_by_id:
            return inputs.research_briefs_by_id[artifact_id]
    return None


def _find_evidence_assessment(
    *,
    inputs: LoadedPortfolioInputs,
    signal: Signal,
) -> EvidenceAssessment | None:
    """Resolve the primary evidence assessment referenced by a signal lineage when available."""

    for artifact_id in signal.lineage.research_artifact_ids:
        if artifact_id in inputs.evidence_assessments_by_id:
            return inputs.evidence_assessments_by_id[artifact_id]
    return None


def _supporting_links_from_hypothesis(
    *,
    inputs: LoadedPortfolioInputs,
    signal: Signal,
) -> list[SupportingEvidenceLink]:
    """Resolve supporting links directly from the linked hypothesis when no brief exists."""

    hypothesis = inputs.hypotheses_by_id.get(signal.hypothesis_id)
    if hypothesis is None:
        return []
    return hypothesis.supporting_evidence_links


def _target_horizon(*, inputs: LoadedPortfolioInputs, signal: Signal) -> str:
    """Resolve a position horizon from the linked hypothesis when available."""

    hypothesis = inputs.hypotheses_by_id.get(signal.hypothesis_id)
    if hypothesis is not None:
        return hypothesis.time_horizon
    return "next_1_4_quarters"
