from __future__ import annotations

from libraries.core import build_provenance
from libraries.schemas import (
    Company,
    ConstraintResult,
    ConstraintSet,
    ConstraintType,
    ConstructionDecision,
    ContributionBreakdown,
    PortfolioAttribution,
    PortfolioConstraint,
    PortfolioProposal,
    PortfolioSelectionSummary,
    PositionAttribution,
    PositionSizingRationale,
    Signal,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id


def build_position_attributions(
    *,
    portfolio_proposal: PortfolioProposal,
    signals_by_id: dict[str, Signal],
    companies_by_id: dict[str, Company],
    constraint_results: list[ConstraintResult],
    position_sizing_rationales: list[PositionSizingRationale],
    construction_decisions: list[ConstructionDecision],
    clock: Clock,
    workflow_run_id: str,
) -> list[PositionAttribution]:
    """Build one structured attribution artifact per position idea."""

    now = clock.now()
    single_name_constraint = _constraint_by_type(
        constraints=portfolio_proposal.constraints,
        constraint_type=ConstraintType.SINGLE_NAME,
    )
    position_sizing_rationales_by_id = {
        rationale.position_sizing_rationale_id: rationale
        for rationale in position_sizing_rationales
    }
    construction_decisions_by_id = {
        decision.construction_decision_id: decision for decision in construction_decisions
    }
    constraint_results_by_id = {
        result.constraint_result_id: result for result in constraint_results
    }
    position_attributions: list[PositionAttribution] = []
    for idea in portfolio_proposal.position_ideas:
        signal = signals_by_id.get(idea.signal_id)
        company = companies_by_id.get(idea.company_id)
        sizing_rationale = (
            position_sizing_rationales_by_id.get(idea.position_sizing_rationale_id)
            if idea.position_sizing_rationale_id is not None
            else None
        )
        construction_decision = (
            construction_decisions_by_id.get(idea.construction_decision_id)
            if idea.construction_decision_id is not None
            else None
        )
        contribution_breakdowns = [
            ContributionBreakdown(
                contributor_type="position_idea",
                contributor_id=idea.position_idea_id,
                metric_name="proposed_weight_bps",
                metric_value=float(idea.proposed_weight_bps),
                unit="bps",
                summary=f"Position idea `{idea.position_idea_id}` contributes {idea.proposed_weight_bps} bps of target weight.",
            ),
            ContributionBreakdown(
                contributor_type="position_idea",
                contributor_id=idea.position_idea_id,
                metric_name="supporting_evidence_link_count",
                metric_value=float(len(idea.supporting_evidence_link_ids)),
                unit="count",
                summary=f"Position idea `{idea.position_idea_id}` is grounded by {len(idea.supporting_evidence_link_ids)} supporting evidence links.",
            ),
        ]
        if signal is not None:
            contribution_breakdowns.append(
                ContributionBreakdown(
                    contributor_type="signal",
                    contributor_id=signal.signal_id,
                    metric_name="primary_score",
                    metric_value=signal.primary_score,
                    unit="score",
                    summary=f"Signal `{signal.signal_id}` contributed score {signal.primary_score:.2f} with stance `{signal.stance.value}`.",
                )
            )
        if idea.confidence is not None:
            contribution_breakdowns.extend(
                [
                    ContributionBreakdown(
                        contributor_type="confidence",
                        contributor_id=idea.position_idea_id,
                        metric_name="confidence",
                        metric_value=idea.confidence.confidence,
                        unit="score",
                        summary=f"Position idea `{idea.position_idea_id}` carries confidence {idea.confidence.confidence:.2f}.",
                    ),
                    ContributionBreakdown(
                        contributor_type="confidence",
                        contributor_id=idea.position_idea_id,
                        metric_name="uncertainty",
                        metric_value=idea.confidence.uncertainty,
                        unit="score",
                        summary=f"Position idea `{idea.position_idea_id}` carries uncertainty {idea.confidence.uncertainty:.2f}.",
                    ),
                ]
            )
        if single_name_constraint is not None and single_name_constraint.hard_limit is not None:
            headroom = single_name_constraint.hard_limit - float(idea.proposed_weight_bps)
            contribution_breakdowns.append(
                ContributionBreakdown(
                    contributor_type="constraint",
                    contributor_id=single_name_constraint.portfolio_constraint_id,
                    metric_name="single_name_headroom_bps",
                    metric_value=headroom,
                    unit=single_name_constraint.unit,
                    summary=(
                        f"Single-name headroom versus `{single_name_constraint.portfolio_constraint_id}` is {headroom:.1f} {single_name_constraint.unit}."
                    ),
                )
            )
        if construction_decision is not None:
            contribution_breakdowns.append(
                ContributionBreakdown(
                    contributor_type="construction_decision",
                    contributor_id=construction_decision.construction_decision_id,
                    metric_name="decision_outcome",
                    metric_value=1.0,
                    unit="flag",
                    summary=construction_decision.summary,
                )
            )
        if sizing_rationale is not None:
            contribution_breakdowns.extend(
                [
                    ContributionBreakdown(
                        contributor_type="position_sizing_rationale",
                        contributor_id=sizing_rationale.position_sizing_rationale_id,
                        metric_name="base_weight_bps",
                        metric_value=float(sizing_rationale.base_weight_bps),
                        unit="bps",
                        summary=(
                            f"Sizing started from {sizing_rationale.base_weight_bps} bps before explicit caps were applied."
                        ),
                    ),
                    ContributionBreakdown(
                        contributor_type="position_sizing_rationale",
                        contributor_id=sizing_rationale.position_sizing_rationale_id,
                        metric_name="final_weight_bps",
                        metric_value=float(sizing_rationale.final_weight_bps),
                        unit="bps",
                        summary=sizing_rationale.summary,
                    ),
                ]
            )
        if construction_decision is not None:
            for constraint_result_id in construction_decision.constraint_result_ids:
                constraint_result = constraint_results_by_id.get(constraint_result_id)
                if constraint_result is None or not constraint_result.binding:
                    continue
                contribution_breakdowns.append(
                    ContributionBreakdown(
                        contributor_type="constraint_result",
                        contributor_id=constraint_result.constraint_result_id,
                        metric_name="binding_constraint",
                        metric_value=1.0,
                        unit="flag",
                        summary=constraint_result.message,
                    )
                )
        if company is not None and company.sector is not None:
            contribution_breakdowns.append(
                ContributionBreakdown(
                    contributor_type="sector",
                    contributor_id=company.company_id,
                    metric_name="sector_membership",
                    metric_value=1.0,
                    unit="flag",
                    summary=f"Company `{company.company_id}` contributes to sector `{company.sector}`.",
                )
            )

        position_attributions.append(
            PositionAttribution(
                position_attribution_id=make_canonical_id(
                    "posattr",
                    portfolio_proposal.portfolio_proposal_id,
                    idea.position_idea_id,
                ),
                portfolio_proposal_id=portfolio_proposal.portfolio_proposal_id,
                position_idea_id=idea.position_idea_id,
                company_id=idea.company_id,
                signal_id=idea.signal_id,
                portfolio_constraint_ids=[
                    constraint.portfolio_constraint_id
                    for constraint in portfolio_proposal.constraints
                ],
                supporting_evidence_link_ids=list(idea.supporting_evidence_link_ids),
                from_arbitrated_signal=(
                    idea.signal_bundle_id is not None and idea.arbitration_decision_id is not None
                ),
                contribution_breakdowns=contribution_breakdowns,
                summary=(
                    f"Position `{idea.position_idea_id}` expresses `{idea.side.value}` on `{idea.symbol}` at {idea.proposed_weight_bps} bps from "
                    f"{'an arbitrated primary signal' if idea.signal_bundle_id is not None and idea.arbitration_decision_id is not None else 'a raw signal fallback'}."
                ),
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day20_position_attribution",
                    source_reference_ids=idea.provenance.source_reference_ids,
                    upstream_artifact_ids=[
                        idea.position_idea_id,
                        idea.signal_id,
                        *idea.supporting_evidence_link_ids,
                    ],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=now,
                updated_at=now,
            )
        )
    return position_attributions


def build_portfolio_attribution(
    *,
    portfolio_proposal: PortfolioProposal,
    position_attributions: list[PositionAttribution],
    companies_by_id: dict[str, Company],
    constraint_set: ConstraintSet | None,
    constraint_results: list[ConstraintResult],
    construction_decisions: list[ConstructionDecision],
    portfolio_selection_summary: PortfolioSelectionSummary | None,
    clock: Clock,
    workflow_run_id: str,
) -> PortfolioAttribution:
    """Build one structured attribution artifact for the whole proposal."""

    now = clock.now()
    gross_exposure = portfolio_proposal.exposure_summary.gross_exposure_bps
    dominant_positions = sorted(
        portfolio_proposal.position_ideas,
        key=lambda idea: abs(idea.proposed_weight_bps),
        reverse=True,
    )
    dominant_position_idea_ids = [idea.position_idea_id for idea in dominant_positions[:3]]
    contribution_breakdowns: list[ContributionBreakdown] = [
        ContributionBreakdown(
            contributor_type="exposure_summary",
            contributor_id=portfolio_proposal.exposure_summary.portfolio_exposure_summary_id,
            metric_name="gross_exposure_bps",
            metric_value=float(portfolio_proposal.exposure_summary.gross_exposure_bps),
            unit="bps",
            summary=(
                f"Proposal gross exposure is {portfolio_proposal.exposure_summary.gross_exposure_bps} bps across "
                f"{portfolio_proposal.exposure_summary.position_count} positions."
            ),
        ),
        ContributionBreakdown(
            contributor_type="exposure_summary",
            contributor_id=portfolio_proposal.exposure_summary.portfolio_exposure_summary_id,
            metric_name="net_exposure_bps",
            metric_value=float(portfolio_proposal.exposure_summary.net_exposure_bps),
            unit="bps",
            summary=f"Proposal net exposure is {portfolio_proposal.exposure_summary.net_exposure_bps} bps.",
        ),
        ContributionBreakdown(
            contributor_type="exposure_summary",
            contributor_id=portfolio_proposal.exposure_summary.portfolio_exposure_summary_id,
            metric_name="cash_buffer_bps",
            metric_value=float(portfolio_proposal.exposure_summary.cash_buffer_bps),
            unit="bps",
            summary=f"Cash buffer remains {portfolio_proposal.exposure_summary.cash_buffer_bps} bps.",
        ),
    ]
    if portfolio_selection_summary is not None:
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="portfolio_selection_summary",
                contributor_id=portfolio_selection_summary.portfolio_selection_summary_id,
                metric_name="candidate_signal_count",
                metric_value=float(len(portfolio_selection_summary.candidate_signal_ids)),
                unit="count",
                summary=portfolio_selection_summary.summary,
            )
        )
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="portfolio_selection_summary",
                contributor_id=portfolio_selection_summary.portfolio_selection_summary_id,
                metric_name="rejected_signal_count",
                metric_value=float(len(portfolio_selection_summary.rejected_signal_ids)),
                unit="count",
                summary=(
                    f"Construction explicitly rejected {len(portfolio_selection_summary.rejected_signal_ids)} candidate signals."
                ),
            )
        )
    if construction_decisions:
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="construction_decision",
                contributor_id=portfolio_proposal.portfolio_proposal_id,
                metric_name="construction_decision_count",
                metric_value=float(len(construction_decisions)),
                unit="count",
                summary=(
                    f"Construction recorded {len(construction_decisions)} explicit include or reject decisions for the proposal context."
                ),
            )
        )
    if constraint_set is not None:
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="constraint_set",
                contributor_id=constraint_set.constraint_set_id,
                metric_name="applied_constraint_count",
                metric_value=float(len(constraint_set.portfolio_constraint_ids)),
                unit="count",
                summary=constraint_set.summary,
            )
        )
    if dominant_positions:
        top_position = dominant_positions[0]
        top_share_pct = (
            (abs(top_position.proposed_weight_bps) / gross_exposure) * 100.0
            if gross_exposure > 0
            else 0.0
        )
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="position_idea",
                contributor_id=top_position.position_idea_id,
                metric_name="top_position_share_pct_of_gross",
                metric_value=top_share_pct,
                unit="pct",
                summary=(
                    f"Top position `{top_position.position_idea_id}` represents {top_share_pct:.1f}% of gross exposure."
                ),
            )
        )
    else:
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="portfolio_proposal",
                contributor_id=portfolio_proposal.portfolio_proposal_id,
                metric_name="position_count",
                metric_value=0.0,
                unit="count",
                summary="Proposal contains no position ideas, so attribution reflects an empty review-bound proposal.",
            )
        )

    for constraint in portfolio_proposal.constraints:
        observed = _observed_constraint_value(
            portfolio_proposal=portfolio_proposal,
            constraint=constraint,
            companies_by_id=companies_by_id,
        )
        if observed is None or constraint.hard_limit is None:
            continue
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="constraint",
                contributor_id=constraint.portfolio_constraint_id,
                metric_name="constraint_headroom",
                metric_value=constraint.hard_limit - observed,
                unit=constraint.unit,
                summary=(
                    f"Constraint `{constraint.portfolio_constraint_id}` has {constraint.hard_limit - observed:.1f} {constraint.unit} of remaining headroom."
                ),
            )
        )
    for constraint_result in constraint_results:
        if (
            constraint_result.subject_type != "portfolio_proposal"
            or constraint_result.subject_id != portfolio_proposal.portfolio_proposal_id
            or not constraint_result.binding
        ):
            continue
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="constraint_result",
                contributor_id=constraint_result.constraint_result_id,
                metric_name="binding_constraint",
                metric_value=1.0,
                unit="flag",
                summary=constraint_result.message,
            )
        )

    sector_totals: dict[str, int] = {}
    for idea in portfolio_proposal.position_ideas:
        company = companies_by_id.get(idea.company_id)
        if company is None or not company.sector:
            continue
        sector_totals[company.sector] = sector_totals.get(company.sector, 0) + abs(
            idea.proposed_weight_bps
        )
    if sector_totals:
        sector, sector_weight = max(sector_totals.items(), key=lambda item: item[1])
        sector_share_pct = (sector_weight / gross_exposure) * 100.0 if gross_exposure > 0 else 0.0
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="sector",
                contributor_id=sector,
                metric_name="top_sector_share_pct_of_gross",
                metric_value=sector_share_pct,
                unit="pct",
                summary=f"Top sector `{sector}` represents {sector_share_pct:.1f}% of gross exposure.",
            )
        )
        concentration_summary = (
            f"Proposal concentration is led by `{dominant_position_idea_ids[0]}` and sector `{sector}`."
            if dominant_position_idea_ids
            else f"Sector concentration is led by `{sector}`."
        )
    else:
        concentration_summary = (
            f"Proposal concentration is led by `{dominant_position_idea_ids[0]}`; sector concentration is unavailable because company sector metadata is missing."
            if dominant_position_idea_ids
            else "Proposal contains no position ideas; sector concentration is unavailable."
        )

    exposure_summary = (
        f"Gross {portfolio_proposal.exposure_summary.gross_exposure_bps} bps, net {portfolio_proposal.exposure_summary.net_exposure_bps} bps, "
        f"cash buffer {portfolio_proposal.exposure_summary.cash_buffer_bps} bps."
    )
    return PortfolioAttribution(
        portfolio_attribution_id=make_canonical_id(
            "portattr",
            portfolio_proposal.portfolio_proposal_id,
        ),
        portfolio_proposal_id=portfolio_proposal.portfolio_proposal_id,
        position_attribution_ids=[
            attribution.position_attribution_id for attribution in position_attributions
        ],
        signal_ids=[idea.signal_id for idea in portfolio_proposal.position_ideas],
        portfolio_constraint_ids=[
            constraint.portfolio_constraint_id for constraint in portfolio_proposal.constraints
        ],
        dominant_position_idea_ids=dominant_position_idea_ids,
        contribution_breakdowns=contribution_breakdowns,
        concentration_summary=concentration_summary,
        exposure_summary=exposure_summary,
        summary=(
            f"Proposal `{portfolio_proposal.portfolio_proposal_id}` is explained by {len(portfolio_proposal.position_ideas)} positions "
            f"and {len(portfolio_proposal.constraints)} explicit constraints."
        ),
        provenance=build_provenance(
            clock=clock,
            transformation_name="day20_portfolio_attribution",
            source_reference_ids=sorted(
                {
                    source_reference_id
                    for idea in portfolio_proposal.position_ideas
                    for source_reference_id in idea.provenance.source_reference_ids
                }
            ),
            upstream_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *[idea.position_idea_id for idea in portfolio_proposal.position_ideas],
                *[
                    attribution.position_attribution_id for attribution in position_attributions
                ],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _constraint_by_type(
    *,
    constraints: list[PortfolioConstraint],
    constraint_type: ConstraintType,
) -> PortfolioConstraint | None:
    for constraint in constraints:
        if constraint.constraint_type is constraint_type:
            return constraint
    return None


def _observed_constraint_value(
    *,
    portfolio_proposal: PortfolioProposal,
    constraint: PortfolioConstraint,
    companies_by_id: dict[str, Company],
) -> float | None:
    if constraint.constraint_type is ConstraintType.SINGLE_NAME:
        return float(
            max((abs(idea.proposed_weight_bps) for idea in portfolio_proposal.position_ideas), default=0)
        )
    if constraint.constraint_type is ConstraintType.GROSS_EXPOSURE:
        return float(portfolio_proposal.exposure_summary.gross_exposure_bps)
    if constraint.constraint_type is ConstraintType.NET_EXPOSURE:
        return float(abs(portfolio_proposal.exposure_summary.net_exposure_bps))
    if constraint.constraint_type is ConstraintType.TURNOVER:
        return float(portfolio_proposal.exposure_summary.turnover_bps_assumption)
    if constraint.constraint_type is ConstraintType.SECTOR:
        sector_totals: dict[str, int] = {}
        for idea in portfolio_proposal.position_ideas:
            company = companies_by_id.get(idea.company_id)
            if company is None or not company.sector:
                continue
            sector_totals[company.sector] = sector_totals.get(company.sector, 0) + abs(
                idea.proposed_weight_bps
            )
        return float(max(sector_totals.values(), default=0))
    return None
