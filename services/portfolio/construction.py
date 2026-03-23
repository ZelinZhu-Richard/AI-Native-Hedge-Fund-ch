from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    ConstraintResult,
    ConstraintSet,
    ConstraintType,
    ConstructionDecision,
    DerivedArtifactValidationStatus,
    EvidenceAssessment,
    PortfolioConstraint,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
    PortfolioSelectionSummary,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    PositionSizingRationale,
    ProposalRejectionReason,
    ResearchBrief,
    ResearchStance,
    RiskCheckStatus,
    SelectionConflict,
    SelectionRule,
    Signal,
    SignalStatus,
    StrictModel,
    SupportingEvidenceLink,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.portfolio.loaders import LoadedPortfolioInputs


class PortfolioSelectionBuildResult(StrictModel):
    """Structured output of candidate selection and proposal-construction reasoning."""

    selection_rules: list[SelectionRule] = Field(
        default_factory=list,
        description="Deterministic selection rules used during construction.",
    )
    constraint_set: ConstraintSet = Field(description="Applied construction constraint set.")
    constraint_results: list[ConstraintResult] = Field(
        default_factory=list,
        description="Explicit constraint application results.",
    )
    position_sizing_rationales: list[PositionSizingRationale] = Field(
        default_factory=list,
        description="Sizing rationales for included positions.",
    )
    construction_decisions: list[ConstructionDecision] = Field(
        default_factory=list,
        description="Explicit include or reject decisions for candidate signals.",
    )
    selection_conflicts: list[SelectionConflict] = Field(
        default_factory=list,
        description="Explicit candidate conflicts recorded during selection.",
    )
    portfolio_selection_summary: PortfolioSelectionSummary = Field(
        description="Parent construction summary for the proposal."
    )
    position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Included position ideas produced by portfolio construction.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing assumptions, fallback, or empty-input paths.",
    )


@dataclass(frozen=True)
class _CandidateContext:
    signal: Signal
    side: PositionSide
    research_brief: ResearchBrief | None
    evidence_assessment: EvidenceAssessment | None
    evidence_links: list[SupportingEvidenceLink]
    evidence_span_ids: list[str]
    supporting_evidence_link_ids: list[str]
    research_artifact_ids: list[str]
    target_horizon: str
    assumptions: list[str]


def make_portfolio_proposal_id(*, company_id: str, name: str, as_of_time: datetime) -> str:
    """Create the canonical portfolio-proposal identifier used across construction artifacts."""

    return make_canonical_id("proposal", company_id, as_of_time.isoformat(), name)


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


def default_selection_rules(*, clock: Clock, workflow_run_id: str) -> list[SelectionRule]:
    """Build the deterministic Day 25 construction rule definitions."""

    now = clock.now()
    rule_specs = [
        (
            "directional_signal_required",
            "candidate_intake",
            "Signals must express a directional positive or negative stance.",
        ),
        (
            "symbol_required",
            "candidate_intake",
            "Construction requires normalized company ticker metadata for the current tradable path.",
        ),
        (
            "supporting_evidence_required",
            "candidate_intake",
            "Signals must resolve exact supporting evidence links before they can become position ideas.",
        ),
        (
            "single_active_idea_per_company",
            "competition_resolution",
            "At most one active position idea may survive for the current company and tradable symbol path.",
        ),
        (
            "base_weight_from_signal_maturity",
            "sizing",
            "Approved and validated signals start at 500 bps; all other eligible signals start at 300 bps.",
        ),
        (
            "single_name_cap",
            "constraint_application",
            "Single-name hard limits may cap a candidate's final position size.",
        ),
        (
            "gross_exposure_hard_limit",
            "constraint_application",
            "Candidates are rejected when they would breach the proposal gross-exposure hard limit.",
        ),
        (
            "net_exposure_hard_limit",
            "constraint_application",
            "Candidates are rejected when they would breach the proposal net-exposure hard limit.",
        ),
        (
            "turnover_hard_limit",
            "constraint_application",
            "Candidates are rejected when flat-start turnover would breach the proposal turnover hard limit.",
        ),
    ]
    return [
        SelectionRule(
            selection_rule_id=make_canonical_id("selrule", rule_name),
            rule_name=rule_name,
            rule_stage=rule_stage,
            description=description,
            active=True,
            notes=[],
            provenance=build_provenance(
                clock=clock,
                transformation_name="day25_default_selection_rules",
                workflow_run_id=workflow_run_id,
                notes=[f"rule_name={rule_name}"],
            ),
            created_at=now,
            updated_at=now,
        )
        for rule_name, rule_stage, description in rule_specs
    ]


def build_portfolio_selection(
    *,
    inputs: LoadedPortfolioInputs,
    proposal_id: str,
    constraints: list[PortfolioConstraint],
    as_of_time: datetime,
    clock: Clock,
    workflow_run_id: str,
) -> PortfolioSelectionBuildResult:
    """Select inspectable proposal candidates and persist explicit construction reasoning."""

    selection_rules = default_selection_rules(clock=clock, workflow_run_id=workflow_run_id)
    rule_id_by_name = {rule.rule_name: rule.selection_rule_id for rule in selection_rules}
    summary_id = make_canonical_id("psummary", proposal_id)
    assumptions = _selection_assumptions(inputs=inputs)
    now = clock.now()
    notes = list(inputs.notes)
    constraint_set = ConstraintSet(
        constraint_set_id=make_canonical_id("constraintset", proposal_id),
        portfolio_proposal_id=proposal_id,
        portfolio_constraint_ids=[
            constraint.portfolio_constraint_id for constraint in constraints if constraint.active
        ],
        selection_rule_ids=[rule.selection_rule_id for rule in selection_rules],
        assumptions=assumptions,
        summary=(
            f"Applied {len(selection_rules)} deterministic selection rules and "
            f"{len([constraint for constraint in constraints if constraint.active])} active portfolio constraints."
        ),
        provenance=build_provenance(
            clock=clock,
            transformation_name="day25_constraint_set",
            workflow_run_id=workflow_run_id,
            notes=assumptions,
        ),
        created_at=now,
        updated_at=now,
    )

    position_ideas: list[PositionIdea] = []
    constraint_results: list[ConstraintResult] = []
    position_sizing_rationales: list[PositionSizingRationale] = []
    construction_decisions: list[ConstructionDecision] = []
    selection_conflicts: list[SelectionConflict] = []
    candidate_signal_ids = [signal.signal_id for signal in inputs.signals]
    company_ticker = inputs.company.ticker if inputs.company is not None else None

    if (
        inputs.signal_bundle is not None
        and inputs.arbitration_decision is not None
        and inputs.arbitration_decision.selected_primary_signal_id is None
    ):
        notes.append(
            "Signal arbitration intentionally withheld a primary signal selection, so construction recorded an empty review-bound proposal context."
        )
        return PortfolioSelectionBuildResult(
            selection_rules=selection_rules,
            constraint_set=constraint_set,
            constraint_results=[],
            position_sizing_rationales=[],
            construction_decisions=[],
            selection_conflicts=[],
            portfolio_selection_summary=PortfolioSelectionSummary(
                portfolio_selection_summary_id=summary_id,
                portfolio_proposal_id=proposal_id,
                company_id=inputs.company_id,
                constraint_set_id=constraint_set.constraint_set_id,
                selection_rule_ids=[rule.selection_rule_id for rule in selection_rules],
                construction_decision_ids=[],
                selection_conflict_ids=[],
                candidate_signal_ids=[],
                included_signal_ids=[],
                included_position_idea_ids=[],
                rejected_signal_ids=[],
                binding_constraint_ids=[],
                assumptions=assumptions,
                summary=(
                    "Signal arbitration withheld actionable input, so the proposal remained empty and review-bound."
                ),
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day25_portfolio_selection_summary",
                    workflow_run_id=workflow_run_id,
                    notes=assumptions,
                ),
                created_at=now,
                updated_at=now,
            ),
            position_ideas=[],
            notes=notes,
        )

    if not candidate_signal_ids:
        notes.append("No actionable signals were available for portfolio construction.")

    ranked_candidates: list[_CandidateContext] = []
    for signal in inputs.signals:
        candidate_assumptions = _candidate_assumptions(inputs=inputs, signal=signal)
        if signal.status not in {SignalStatus.CANDIDATE, SignalStatus.APPROVED}:
            construction_decisions.append(
                _build_rejected_construction_decision(
                    summary_id=summary_id,
                    company_id=inputs.company_id,
                    signal=signal,
                    rule_ids=[rule_id_by_name["base_weight_from_signal_maturity"]],
                    rejection_reasons=[
                        ProposalRejectionReason(
                            reason_code="signal_status_ineligible",
                            message=(
                                f"Signal status `{signal.status.value}` is not eligible for portfolio construction."
                            ),
                            blocking=True,
                            related_constraint_ids=[],
                            related_artifact_ids=[signal.signal_id],
                        )
                    ],
                    constraint_results=[],
                    assumptions=candidate_assumptions,
                    summary=(
                        f"Rejected signal `{signal.signal_id}` because status `{signal.status.value}` is not eligible for portfolio construction."
                    ),
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
            continue
        if signal.stance in {ResearchStance.MIXED, ResearchStance.MONITOR}:
            construction_decisions.append(
                _build_rejected_construction_decision(
                    summary_id=summary_id,
                    company_id=inputs.company_id,
                    signal=signal,
                    rule_ids=[rule_id_by_name["directional_signal_required"]],
                    rejection_reasons=[
                        ProposalRejectionReason(
                            reason_code="non_directional_stance",
                            message=(
                                f"Signal stance `{signal.stance.value}` does not express a directional portfolio view."
                            ),
                            blocking=False,
                            related_constraint_ids=[],
                            related_artifact_ids=[signal.signal_id],
                        )
                    ],
                    constraint_results=[],
                    assumptions=candidate_assumptions,
                    summary=(
                        f"Rejected signal `{signal.signal_id}` because stance `{signal.stance.value}` is not directional."
                    ),
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
            continue
        if not company_ticker:
            construction_decisions.append(
                _build_rejected_construction_decision(
                    summary_id=summary_id,
                    company_id=inputs.company_id,
                    signal=signal,
                    rule_ids=[rule_id_by_name["symbol_required"]],
                    rejection_reasons=[
                        ProposalRejectionReason(
                            reason_code="missing_symbol",
                            message=(
                                "Normalized company metadata did not provide a tradable symbol for the current company."
                            ),
                            blocking=True,
                            related_constraint_ids=[],
                            related_artifact_ids=[signal.signal_id],
                        )
                    ],
                    constraint_results=[],
                    assumptions=candidate_assumptions,
                    summary=(
                        f"Rejected signal `{signal.signal_id}` because no tradable symbol was available."
                    ),
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
            continue

        research_brief = _find_research_brief(inputs=inputs, signal=signal)
        evidence_assessment = _find_evidence_assessment(inputs=inputs, signal=signal)
        evidence_links = (
            research_brief.supporting_evidence_links
            if research_brief is not None
            else _supporting_links_from_hypothesis(inputs=inputs, signal=signal)
        )
        if not evidence_links:
            construction_decisions.append(
                _build_rejected_construction_decision(
                    summary_id=summary_id,
                    company_id=inputs.company_id,
                    signal=signal,
                    rule_ids=[rule_id_by_name["supporting_evidence_required"]],
                    rejection_reasons=[
                        ProposalRejectionReason(
                            reason_code="missing_supporting_evidence",
                            message=(
                                "No exact supporting evidence links could be resolved from the linked research artifacts."
                            ),
                            blocking=True,
                            related_constraint_ids=[],
                            related_artifact_ids=[signal.signal_id, signal.hypothesis_id],
                        )
                    ],
                    constraint_results=[],
                    assumptions=candidate_assumptions,
                    summary=(
                        f"Rejected signal `{signal.signal_id}` because no exact supporting evidence links were available."
                    ),
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
            continue

        ranked_candidates.append(
            _CandidateContext(
                signal=signal,
                side=(
                    PositionSide.LONG
                    if signal.stance is ResearchStance.POSITIVE
                    else PositionSide.SHORT
                ),
                research_brief=research_brief,
                evidence_assessment=evidence_assessment,
                evidence_links=evidence_links,
                evidence_span_ids=sorted({link.evidence_span_id for link in evidence_links}),
                supporting_evidence_link_ids=sorted(
                    {link.supporting_evidence_link_id for link in evidence_links}
                ),
                research_artifact_ids=sorted(
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
                ),
                target_horizon=_target_horizon(inputs=inputs, signal=signal),
                assumptions=candidate_assumptions,
            )
        )

    ranked_candidates.sort(
        key=lambda candidate: (
            _candidate_priority(inputs=inputs, signal=candidate.signal),
            _maturity_bucket(candidate.signal),
            abs(candidate.signal.primary_score),
            candidate.signal.effective_at,
            candidate.signal.signal_id,
        ),
        reverse=True,
    )

    if ranked_candidates:
        top_substantive_key = _substantive_rank_key(inputs=inputs, signal=ranked_candidates[0].signal)
        top_tied_candidates = [
            candidate
            for candidate in ranked_candidates
            if _substantive_rank_key(inputs=inputs, signal=candidate.signal) == top_substantive_key
        ]
        top_tied_stances = {candidate.signal.stance for candidate in top_tied_candidates}
        if len(top_tied_candidates) > 1 and len(top_tied_stances) > 1:
            conflict = SelectionConflict(
                selection_conflict_id=make_canonical_id(
                    "sconflict",
                    summary_id,
                    "unresolved_opposing_tie",
                ),
                portfolio_selection_summary_id=summary_id,
                company_id=inputs.company_id,
                conflict_kind="unresolved_opposing_tie",
                candidate_signal_ids=[candidate.signal.signal_id for candidate in top_tied_candidates],
                resolved_in_favor_of_signal_id=None,
                summary=(
                    "Top-ranked opposing signals tied on substantive construction ranking keys, so construction rejected all same-company candidates rather than break the tie implicitly."
                ),
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day25_selection_conflict",
                    upstream_artifact_ids=[
                        candidate.signal.signal_id for candidate in top_tied_candidates
                    ],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=now,
                updated_at=now,
            )
            selection_conflicts.append(conflict)
            for candidate in ranked_candidates:
                construction_decisions.append(
                    _build_rejected_construction_decision(
                        summary_id=summary_id,
                        company_id=inputs.company_id,
                        signal=candidate.signal,
                        rule_ids=[rule_id_by_name["single_active_idea_per_company"]],
                        rejection_reasons=[
                            ProposalRejectionReason(
                                reason_code=(
                                    "unresolved_opposing_tie"
                                    if candidate in top_tied_candidates
                                    else "higher_priority_conflict_unresolved"
                                ),
                                message=(
                                    "A higher-priority same-company conflict remained unresolved."
                                    if candidate not in top_tied_candidates
                                    else "Top-ranked opposing signals tied on substantive keys, so the conflict remained unresolved."
                                ),
                                blocking=True,
                                related_constraint_ids=[],
                                related_artifact_ids=[conflict.selection_conflict_id],
                            )
                        ],
                        constraint_results=[],
                        assumptions=candidate.assumptions,
                        summary=(
                            f"Rejected signal `{candidate.signal.signal_id}` because same-company directional competition remained unresolved."
                        ),
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                    )
                )
            notes.append(
                "Same-company construction candidates tied across opposing directions, so portfolio construction rejected all candidates rather than choose implicitly."
            )
        else:
            selected_candidate: _CandidateContext | None = None
            selected_decision: ConstructionDecision | None = None
            selected_position_idea: PositionIdea | None = None
            selected_rationale: PositionSizingRationale | None = None
            selected_constraint_results: list[ConstraintResult] = []
            single_name_constraint = _constraint_by_type(
                constraints=constraints,
                constraint_type=ConstraintType.SINGLE_NAME,
            )
            for candidate in ranked_candidates:
                base_weight_bps = _base_weight_bps(signal=candidate.signal)
                final_weight_bps = base_weight_bps
                candidate_constraint_results: list[ConstraintResult] = []
                binding_constraint_ids: list[str] = []

                if single_name_constraint is not None:
                    single_name_result, final_weight_bps = _single_name_constraint_result(
                        constraint_set_id=constraint_set.constraint_set_id,
                        subject_id=candidate.signal.signal_id,
                        signal=candidate.signal,
                        base_weight_bps=base_weight_bps,
                        max_weight_bps=500,
                        constraint=single_name_constraint,
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                    )
                    candidate_constraint_results.append(single_name_result)
                    if single_name_result.binding:
                        binding_constraint_ids.append(single_name_constraint.portfolio_constraint_id)

                projected_constraint_results = _project_portfolio_constraint_results(
                    constraint_set_id=constraint_set.constraint_set_id,
                    proposal_id=proposal_id,
                    current_position_ideas=position_ideas,
                    candidate=candidate,
                    final_weight_bps=final_weight_bps,
                    constraints=constraints,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
                candidate_constraint_results.extend(projected_constraint_results)
                binding_constraint_ids.extend(
                    result.portfolio_constraint_id
                    for result in candidate_constraint_results
                    if result.binding
                )
                candidate_constraint_results = list(
                    {
                        result.constraint_result_id: result
                        for result in candidate_constraint_results
                    }.values()
                )

                failing_constraint_results = [
                    result
                    for result in candidate_constraint_results
                    if result.status is RiskCheckStatus.FAIL
                ]
                if failing_constraint_results:
                    constraint_results.extend(candidate_constraint_results)
                    construction_decisions.append(
                        _build_rejected_construction_decision(
                            summary_id=summary_id,
                            company_id=inputs.company_id,
                            signal=candidate.signal,
                            rule_ids=[
                                rule_id_by_name["base_weight_from_signal_maturity"],
                                rule_id_by_name["single_name_cap"],
                                rule_id_by_name["gross_exposure_hard_limit"],
                                rule_id_by_name["net_exposure_hard_limit"],
                                rule_id_by_name["turnover_hard_limit"],
                            ],
                            rejection_reasons=[
                                ProposalRejectionReason(
                                    reason_code="portfolio_constraint_breach",
                                    message=result.message,
                                    blocking=True,
                                    related_constraint_ids=[result.portfolio_constraint_id],
                                    related_artifact_ids=[result.constraint_result_id],
                                )
                                for result in failing_constraint_results
                            ],
                            constraint_results=candidate_constraint_results,
                            assumptions=candidate.assumptions,
                            summary=(
                                f"Rejected signal `{candidate.signal.signal_id}` because it would breach one or more active portfolio constraints."
                            ),
                            clock=clock,
                            workflow_run_id=workflow_run_id,
                        )
                    )
                    continue

                position_idea_id = make_canonical_id(
                    "idea",
                    candidate.signal.signal_id,
                    candidate.signal.stance.value,
                    as_of_time.isoformat(),
                )
                sizing_rationale_id = make_canonical_id("psize", position_idea_id)
                decision_id = make_canonical_id("cdecision", summary_id, candidate.signal.signal_id)
                position_idea = PositionIdea(
                    position_idea_id=position_idea_id,
                    company_id=inputs.company_id,
                    signal_id=candidate.signal.signal_id,
                    symbol=company_ticker or "UNKNOWN",
                    instrument_type="equity",
                    side=candidate.side,
                    thesis_summary=candidate.signal.thesis_summary,
                    selection_reason=_selection_reason(inputs=inputs, signal=candidate.signal),
                    entry_conditions=[
                        "Human review completed.",
                        "Blocking portfolio risk checks resolved.",
                    ],
                    exit_conditions=[
                        "Signal stance is withdrawn or flips direction.",
                        "New evidence invalidates the core hypothesis.",
                    ],
                    target_horizon=candidate.target_horizon,
                    proposed_weight_bps=final_weight_bps,
                    max_weight_bps=500,
                    evidence_span_ids=candidate.evidence_span_ids,
                    supporting_evidence_link_ids=candidate.supporting_evidence_link_ids,
                    research_artifact_ids=candidate.research_artifact_ids,
                    review_decision_ids=[],
                    signal_bundle_id=(
                        inputs.signal_bundle.signal_bundle_id
                        if inputs.signal_bundle is not None
                        else None
                    ),
                    arbitration_decision_id=(
                        inputs.arbitration_decision.arbitration_decision_id
                        if inputs.arbitration_decision is not None
                        else None
                    ),
                    construction_decision_id=decision_id,
                    position_sizing_rationale_id=sizing_rationale_id,
                    status=PositionIdeaStatus.PENDING_REVIEW,
                    confidence=candidate.signal.confidence,
                    provenance=build_provenance(
                        clock=clock,
                        transformation_name="day25_signal_to_position_mapping",
                        source_reference_ids=candidate.signal.provenance.source_reference_ids,
                        upstream_artifact_ids=[
                            candidate.signal.signal_id,
                            *candidate.research_artifact_ids,
                        ],
                        workflow_run_id=workflow_run_id,
                        notes=[
                            f"signal_status={candidate.signal.status.value}",
                            (
                                "portfolio_construction_input=arbitrated_primary_candidate"
                                if inputs.arbitration_decision is not None
                                and inputs.arbitration_decision.selected_primary_signal_id
                                == candidate.signal.signal_id
                                else "portfolio_construction_input=ranked_candidate"
                            ),
                        ],
                    ),
                    created_at=now,
                    updated_at=now,
                )
                sizing_rationale = PositionSizingRationale(
                    position_sizing_rationale_id=sizing_rationale_id,
                    position_idea_id=position_idea_id,
                    signal_id=candidate.signal.signal_id,
                    base_weight_bps=base_weight_bps,
                    final_weight_bps=final_weight_bps,
                    max_weight_bps=500,
                    sizing_rule_name="base_weight_from_signal_maturity",
                    binding_constraint_ids=sorted(set(binding_constraint_ids)),
                    assumptions=candidate.assumptions,
                    summary=(
                        f"Position `{position_idea_id}` started at {base_weight_bps} bps and finished at {final_weight_bps} bps after explicit construction constraints were applied."
                    ),
                    provenance=build_provenance(
                        clock=clock,
                        transformation_name="day25_position_sizing_rationale",
                        source_reference_ids=candidate.signal.provenance.source_reference_ids,
                        upstream_artifact_ids=[
                            position_idea_id,
                            candidate.signal.signal_id,
                            *[result.constraint_result_id for result in candidate_constraint_results],
                        ],
                        workflow_run_id=workflow_run_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
                decision = ConstructionDecision(
                    construction_decision_id=decision_id,
                    portfolio_selection_summary_id=summary_id,
                    company_id=inputs.company_id,
                    signal_id=candidate.signal.signal_id,
                    decision_outcome="included",
                    position_idea_id=position_idea_id,
                    position_sizing_rationale_id=sizing_rationale_id,
                    selection_rule_ids=[
                        rule_id_by_name["directional_signal_required"],
                        rule_id_by_name["symbol_required"],
                        rule_id_by_name["supporting_evidence_required"],
                        rule_id_by_name["single_active_idea_per_company"],
                        rule_id_by_name["base_weight_from_signal_maturity"],
                        rule_id_by_name["single_name_cap"],
                        rule_id_by_name["gross_exposure_hard_limit"],
                        rule_id_by_name["net_exposure_hard_limit"],
                        rule_id_by_name["turnover_hard_limit"],
                    ],
                    constraint_result_ids=[
                        result.constraint_result_id for result in candidate_constraint_results
                    ],
                    proposal_rejection_reasons=[],
                    assumptions=candidate.assumptions,
                    summary=(
                        f"Included signal `{candidate.signal.signal_id}` as the surviving same-company construction candidate at {final_weight_bps} bps."
                    ),
                    provenance=build_provenance(
                        clock=clock,
                        transformation_name="day25_construction_decision",
                        source_reference_ids=candidate.signal.provenance.source_reference_ids,
                        upstream_artifact_ids=[
                            candidate.signal.signal_id,
                            position_idea_id,
                            sizing_rationale_id,
                            *[result.constraint_result_id for result in candidate_constraint_results],
                        ],
                        workflow_run_id=workflow_run_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
                selected_candidate = candidate
                selected_position_idea = position_idea
                selected_rationale = sizing_rationale
                selected_decision = decision
                selected_constraint_results = candidate_constraint_results
                break

            if selected_candidate is not None and selected_position_idea is not None and selected_rationale is not None and selected_decision is not None:
                position_ideas.append(selected_position_idea)
                position_sizing_rationales.append(selected_rationale)
                construction_decisions.append(selected_decision)
                constraint_results.extend(selected_constraint_results)

                if len(ranked_candidates) > 1:
                    conflict = SelectionConflict(
                        selection_conflict_id=make_canonical_id(
                            "sconflict",
                            summary_id,
                            "same_company_candidate_competition",
                        ),
                        portfolio_selection_summary_id=summary_id,
                        company_id=inputs.company_id,
                        conflict_kind="same_company_candidate_competition",
                        candidate_signal_ids=[
                            candidate.signal.signal_id for candidate in ranked_candidates
                        ],
                        resolved_in_favor_of_signal_id=selected_candidate.signal.signal_id,
                        summary=(
                            f"Same-company candidates competed for one active slot; signal `{selected_candidate.signal.signal_id}` survived the ranked construction process."
                        ),
                        provenance=build_provenance(
                            clock=clock,
                            transformation_name="day25_selection_conflict",
                            upstream_artifact_ids=[
                                candidate.signal.signal_id for candidate in ranked_candidates
                            ],
                            workflow_run_id=workflow_run_id,
                        ),
                        created_at=now,
                        updated_at=now,
                    )
                    selection_conflicts.append(conflict)
                    for candidate in ranked_candidates:
                        if candidate.signal.signal_id == selected_candidate.signal.signal_id:
                            continue
                        construction_decisions.append(
                            _build_rejected_construction_decision(
                                summary_id=summary_id,
                                company_id=inputs.company_id,
                                signal=candidate.signal,
                                rule_ids=[rule_id_by_name["single_active_idea_per_company"]],
                                rejection_reasons=[
                                    ProposalRejectionReason(
                                        reason_code="lower_ranked_same_company_candidate",
                                        message=(
                                            f"Signal `{candidate.signal.signal_id}` ranked behind the included same-company candidate `{selected_candidate.signal.signal_id}`."
                                        ),
                                        blocking=False,
                                        related_constraint_ids=[],
                                        related_artifact_ids=[
                                            conflict.selection_conflict_id,
                                            selected_candidate.signal.signal_id,
                                        ],
                                    )
                                ],
                                constraint_results=[],
                                assumptions=candidate.assumptions,
                                summary=(
                                    f"Rejected signal `{candidate.signal.signal_id}` because a higher-priority same-company candidate was already selected."
                                ),
                                clock=clock,
                                workflow_run_id=workflow_run_id,
                            )
                        )
            elif ranked_candidates:
                notes.append(
                    "No candidate signals satisfied the active portfolio constraints, so construction recorded only explicit rejection decisions."
                )

    final_constraint_results = _final_portfolio_constraint_results(
        constraint_set_id=constraint_set.constraint_set_id,
        proposal_id=proposal_id,
        position_ideas=position_ideas,
        constraints=constraints,
        clock=clock,
        workflow_run_id=workflow_run_id,
    )
    constraint_results.extend(final_constraint_results)
    binding_constraint_ids = sorted(
        {
            result.portfolio_constraint_id
            for result in constraint_results
            if result.binding
        }
    )
    construction_decisions = list(
        {decision.construction_decision_id: decision for decision in construction_decisions}.values()
    )
    portfolio_selection_summary = PortfolioSelectionSummary(
        portfolio_selection_summary_id=summary_id,
        portfolio_proposal_id=proposal_id,
        company_id=inputs.company_id,
        constraint_set_id=constraint_set.constraint_set_id,
        selection_rule_ids=[rule.selection_rule_id for rule in selection_rules],
        construction_decision_ids=[
            decision.construction_decision_id for decision in construction_decisions
        ],
        selection_conflict_ids=[
            conflict.selection_conflict_id for conflict in selection_conflicts
        ],
        candidate_signal_ids=candidate_signal_ids,
        included_signal_ids=[idea.signal_id for idea in position_ideas],
        included_position_idea_ids=[idea.position_idea_id for idea in position_ideas],
        rejected_signal_ids=[
            decision.signal_id
            for decision in construction_decisions
            if decision.decision_outcome == "rejected"
        ],
        binding_constraint_ids=binding_constraint_ids,
        assumptions=assumptions,
        summary=(
            f"Portfolio construction evaluated {len(candidate_signal_ids)} candidate signals, included {len(position_ideas)} position ideas, and rejected {len([decision for decision in construction_decisions if decision.decision_outcome == 'rejected'])} candidates."
        ),
        provenance=build_provenance(
            clock=clock,
            transformation_name="day25_portfolio_selection_summary",
            upstream_artifact_ids=[
                constraint_set.constraint_set_id,
                *[decision.construction_decision_id for decision in construction_decisions],
                *[conflict.selection_conflict_id for conflict in selection_conflicts],
            ],
            workflow_run_id=workflow_run_id,
            notes=assumptions,
        ),
        created_at=now,
        updated_at=now,
    )
    if position_ideas:
        notes.append(
            f"Portfolio construction selected {len(position_ideas)} included position idea(s) from {len(candidate_signal_ids)} candidate signal(s)."
        )
    return PortfolioSelectionBuildResult(
        selection_rules=selection_rules,
        constraint_set=constraint_set,
        constraint_results=constraint_results,
        position_sizing_rationales=position_sizing_rationales,
        construction_decisions=construction_decisions,
        selection_conflicts=selection_conflicts,
        portfolio_selection_summary=portfolio_selection_summary,
        position_ideas=position_ideas,
        notes=notes,
    )


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
    signal_bundle_id: str | None,
    arbitration_decision_id: str | None,
    clock: Clock,
    workflow_run_id: str,
    portfolio_attribution_id: str | None = None,
    stress_test_run_id: str | None = None,
    portfolio_selection_summary_id: str | None = None,
) -> PortfolioProposal:
    """Build one Day 7 reviewable portfolio proposal from position ideas."""

    proposal_id = make_portfolio_proposal_id(
        company_id=company_id,
        name=name,
        as_of_time=as_of_time,
    )
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
        signal_bundle_id=signal_bundle_id,
        arbitration_decision_id=arbitration_decision_id,
        portfolio_attribution_id=portfolio_attribution_id,
        stress_test_run_id=stress_test_run_id,
        portfolio_selection_summary_id=portfolio_selection_summary_id,
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


def _selection_assumptions(*, inputs: LoadedPortfolioInputs) -> list[str]:
    """Resolve stable assumptions for one portfolio-selection pass."""

    assumptions = ["flat_start_turnover_assumption"]
    if inputs.signal_bundle is None or inputs.arbitration_decision is None:
        assumptions.append("raw_signal_fallback_used")
    elif inputs.arbitration_decision.selected_primary_signal_id is None:
        assumptions.append("arbitration_withheld_actionable_input")
    else:
        assumptions.append("arbitrated_primary_candidate_priority")
    return assumptions


def _candidate_assumptions(*, inputs: LoadedPortfolioInputs, signal: Signal) -> list[str]:
    """Resolve candidate-specific assumptions for one construction decision."""

    assumptions = _selection_assumptions(inputs=inputs)
    if (
        inputs.arbitration_decision is not None
        and inputs.arbitration_decision.selected_primary_signal_id == signal.signal_id
    ):
        assumptions.append("candidate_is_arbitrated_primary_signal")
    return assumptions


def _candidate_priority(*, inputs: LoadedPortfolioInputs, signal: Signal) -> int:
    """Return the primary arbitration-aware candidate priority."""

    if (
        inputs.arbitration_decision is not None
        and inputs.arbitration_decision.selected_primary_signal_id == signal.signal_id
    ):
        return 1
    return 0


def _maturity_bucket(signal: Signal) -> int:
    """Return the deterministic maturity bucket used for construction ranking."""

    if (
        signal.status is SignalStatus.APPROVED
        and signal.validation_status is DerivedArtifactValidationStatus.VALIDATED
    ):
        return 4
    if signal.status is SignalStatus.APPROVED:
        return 3
    if signal.validation_status is DerivedArtifactValidationStatus.VALIDATED:
        return 2
    return 1


def _substantive_rank_key(*, inputs: LoadedPortfolioInputs, signal: Signal) -> tuple[int, int, float, datetime]:
    """Return the ranking key without the deterministic tie-break signal identifier."""

    return (
        _candidate_priority(inputs=inputs, signal=signal),
        _maturity_bucket(signal),
        abs(signal.primary_score),
        signal.effective_at,
    )


def _base_weight_bps(*, signal: Signal) -> int:
    """Return the deterministic base weight for one eligible signal."""

    if (
        signal.status is SignalStatus.APPROVED
        and signal.validation_status is DerivedArtifactValidationStatus.VALIDATED
    ):
        return 500
    return 300


def _selection_reason(*, inputs: LoadedPortfolioInputs, signal: Signal) -> str:
    """Build the operator-readable included-position selection reason."""

    if (
        inputs.arbitration_decision is not None
        and inputs.arbitration_decision.selected_primary_signal_id == signal.signal_id
    ):
        return (
            f"Selected from arbitrated primary signal `{signal.signal_family}` with score "
            f"{signal.primary_score:.2f} and stance `{signal.stance.value}`."
        )
    if inputs.signal_bundle is None or inputs.arbitration_decision is None:
        return (
            f"Selected from raw signal `{signal.signal_family}` with score "
            f"{signal.primary_score:.2f} and stance `{signal.stance.value}` because no arbitrated primary signal was available."
        )
    return (
        f"Selected from ranked signal `{signal.signal_family}` with score "
        f"{signal.primary_score:.2f} and stance `{signal.stance.value}` "
        "under the current review-bound portfolio construction rules."
    )


def _single_name_constraint_result(
    *,
    constraint_set_id: str,
    subject_id: str,
    signal: Signal,
    base_weight_bps: int,
    max_weight_bps: int,
    constraint: PortfolioConstraint,
    clock: Clock,
    workflow_run_id: str,
) -> tuple[ConstraintResult, int]:
    """Apply the single-name hard limit to one candidate."""

    hard_limit = int(constraint.hard_limit or max_weight_bps)
    final_weight_bps = min(base_weight_bps, hard_limit, max_weight_bps)
    binding = final_weight_bps < base_weight_bps or final_weight_bps == hard_limit
    status = RiskCheckStatus.WARN if binding else RiskCheckStatus.PASS
    headroom_value = float(max(hard_limit - final_weight_bps, 0))
    result = ConstraintResult(
        constraint_result_id=make_canonical_id(
            "cresult",
            constraint_set_id,
            subject_id,
            constraint.portfolio_constraint_id,
        ),
        constraint_set_id=constraint_set_id,
        subject_type="candidate_signal",
        subject_id=subject_id,
        portfolio_constraint_id=constraint.portfolio_constraint_id,
        status=status,
        binding=binding,
        observed_value=float(base_weight_bps),
        limit_value=float(hard_limit),
        headroom_value=headroom_value,
        unit=constraint.unit,
        message=(
            f"Single-name limit capped candidate `{signal.signal_id}` from {base_weight_bps} bps to {final_weight_bps} bps."
            if final_weight_bps < base_weight_bps
            else f"Single-name limit left candidate `{signal.signal_id}` at {final_weight_bps} bps."
        ),
        provenance=build_provenance(
            clock=clock,
            transformation_name="day25_constraint_result",
            source_reference_ids=signal.provenance.source_reference_ids,
            upstream_artifact_ids=[signal.signal_id, constraint.portfolio_constraint_id],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return result, final_weight_bps


def _project_portfolio_constraint_results(
    *,
    constraint_set_id: str,
    proposal_id: str,
    current_position_ideas: list[PositionIdea],
    candidate: _CandidateContext,
    final_weight_bps: int,
    constraints: list[PortfolioConstraint],
    clock: Clock,
    workflow_run_id: str,
) -> list[ConstraintResult]:
    """Evaluate projected portfolio-level hard constraints for one candidate."""

    current_long = sum(
        idea.proposed_weight_bps for idea in current_position_ideas if idea.side is PositionSide.LONG
    )
    current_short = sum(
        idea.proposed_weight_bps for idea in current_position_ideas if idea.side is PositionSide.SHORT
    )
    projected_long = current_long + (final_weight_bps if candidate.side is PositionSide.LONG else 0)
    projected_short = current_short + (final_weight_bps if candidate.side is PositionSide.SHORT else 0)
    projected_gross = projected_long + projected_short
    projected_net = projected_long - projected_short
    projected_turnover = projected_gross
    metrics = {
        ConstraintType.GROSS_EXPOSURE: (
            float(projected_gross),
            "Projected gross exposure after including the candidate.",
        ),
        ConstraintType.NET_EXPOSURE: (
            float(abs(projected_net)),
            "Projected absolute net exposure after including the candidate.",
        ),
        ConstraintType.TURNOVER: (
            float(projected_turnover),
            "Projected flat-start turnover after including the candidate.",
        ),
    }
    results: list[ConstraintResult] = []
    for constraint in constraints:
        if not constraint.active or constraint.constraint_type not in metrics:
            continue
        observed_value, description = metrics[constraint.constraint_type]
        if constraint.hard_limit is None:
            continue
        if observed_value > constraint.hard_limit:
            status = RiskCheckStatus.FAIL
            binding = True
        elif observed_value == constraint.hard_limit:
            status = RiskCheckStatus.WARN
            binding = True
        else:
            status = RiskCheckStatus.PASS
            binding = False
        results.append(
            ConstraintResult(
                constraint_result_id=make_canonical_id(
                    "cresult",
                    constraint_set_id,
                    candidate.signal.signal_id,
                    constraint.portfolio_constraint_id,
                ),
                constraint_set_id=constraint_set_id,
                subject_type="candidate_signal",
                subject_id=candidate.signal.signal_id,
                portfolio_constraint_id=constraint.portfolio_constraint_id,
                status=status,
                binding=binding,
                observed_value=observed_value,
                limit_value=float(constraint.hard_limit),
                headroom_value=float(constraint.hard_limit - observed_value),
                unit=constraint.unit,
                message=(
                    f"{description} Candidate `{candidate.signal.signal_id}` would breach `{constraint.portfolio_constraint_id}`."
                    if status is RiskCheckStatus.FAIL
                    else f"{description} Candidate `{candidate.signal.signal_id}` remains within `{constraint.portfolio_constraint_id}`."
                ),
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day25_constraint_result",
                    source_reference_ids=candidate.signal.provenance.source_reference_ids,
                    upstream_artifact_ids=[
                        candidate.signal.signal_id,
                        proposal_id,
                        constraint.portfolio_constraint_id,
                    ],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=clock.now(),
                updated_at=clock.now(),
            )
        )
    return results


def _final_portfolio_constraint_results(
    *,
    constraint_set_id: str,
    proposal_id: str,
    position_ideas: list[PositionIdea],
    constraints: list[PortfolioConstraint],
    clock: Clock,
    workflow_run_id: str,
) -> list[ConstraintResult]:
    """Record final observed construction constraint results for the assembled proposal."""

    long_exposure = sum(
        idea.proposed_weight_bps for idea in position_ideas if idea.side is PositionSide.LONG
    )
    short_exposure = sum(
        idea.proposed_weight_bps for idea in position_ideas if idea.side is PositionSide.SHORT
    )
    gross_exposure = long_exposure + short_exposure
    net_exposure = long_exposure - short_exposure
    turnover = gross_exposure
    max_single_name = max((idea.proposed_weight_bps for idea in position_ideas), default=0)
    metrics = {
        ConstraintType.SINGLE_NAME: (
            float(max_single_name),
            "Final maximum single-name exposure in the proposal.",
        ),
        ConstraintType.GROSS_EXPOSURE: (
            float(gross_exposure),
            "Final gross exposure in the proposal.",
        ),
        ConstraintType.NET_EXPOSURE: (
            float(abs(net_exposure)),
            "Final absolute net exposure in the proposal.",
        ),
        ConstraintType.TURNOVER: (
            float(turnover),
            "Final flat-start turnover assumption in the proposal.",
        ),
    }
    results: list[ConstraintResult] = []
    for constraint in constraints:
        if not constraint.active or constraint.constraint_type not in metrics:
            continue
        observed_value, description = metrics[constraint.constraint_type]
        if constraint.hard_limit is None:
            continue
        if observed_value > constraint.hard_limit:
            status = RiskCheckStatus.FAIL
            binding = True
        elif observed_value == constraint.hard_limit and observed_value > 0:
            status = RiskCheckStatus.WARN
            binding = True
        else:
            status = RiskCheckStatus.PASS
            binding = False
        results.append(
            ConstraintResult(
                constraint_result_id=make_canonical_id(
                    "cresult",
                    constraint_set_id,
                    proposal_id,
                    constraint.portfolio_constraint_id,
                ),
                constraint_set_id=constraint_set_id,
                subject_type="portfolio_proposal",
                subject_id=proposal_id,
                portfolio_constraint_id=constraint.portfolio_constraint_id,
                status=status,
                binding=binding,
                observed_value=observed_value,
                limit_value=float(constraint.hard_limit),
                headroom_value=float(constraint.hard_limit - observed_value),
                unit=constraint.unit,
                message=(
                    f"{description} Final proposal value exceeds `{constraint.portfolio_constraint_id}`."
                    if status is RiskCheckStatus.FAIL
                    else f"{description} Final proposal value remains within `{constraint.portfolio_constraint_id}`."
                ),
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day25_final_constraint_result",
                    upstream_artifact_ids=[
                        proposal_id,
                        *[idea.position_idea_id for idea in position_ideas],
                        constraint.portfolio_constraint_id,
                    ],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=clock.now(),
                updated_at=clock.now(),
            )
        )
    return results


def _build_rejected_construction_decision(
    *,
    summary_id: str,
    company_id: str,
    signal: Signal,
    rule_ids: list[str],
    rejection_reasons: list[ProposalRejectionReason],
    constraint_results: list[ConstraintResult],
    assumptions: list[str],
    summary: str,
    clock: Clock,
    workflow_run_id: str,
) -> ConstructionDecision:
    """Build one explicit rejected construction decision."""

    now = clock.now()
    return ConstructionDecision(
        construction_decision_id=make_canonical_id("cdecision", summary_id, signal.signal_id),
        portfolio_selection_summary_id=summary_id,
        company_id=company_id,
        signal_id=signal.signal_id,
        decision_outcome="rejected",
        position_idea_id=None,
        position_sizing_rationale_id=None,
        selection_rule_ids=rule_ids,
        constraint_result_ids=[result.constraint_result_id for result in constraint_results],
        proposal_rejection_reasons=rejection_reasons,
        assumptions=assumptions,
        summary=summary,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day25_construction_decision",
            source_reference_ids=signal.provenance.source_reference_ids,
            upstream_artifact_ids=[
                signal.signal_id,
                *[result.constraint_result_id for result in constraint_results],
                *[
                    artifact_id
                    for reason in rejection_reasons
                    for artifact_id in reason.related_artifact_ids
                ],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
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


def _constraint_by_type(
    *,
    constraints: list[PortfolioConstraint],
    constraint_type: ConstraintType,
) -> PortfolioConstraint | None:
    """Resolve one active portfolio constraint by type when available."""

    for constraint in constraints:
        if constraint.active and constraint.constraint_type is constraint_type:
            return constraint
    return None
