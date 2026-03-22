from __future__ import annotations

from libraries.core import build_provenance
from libraries.schemas import (
    Company,
    ConstraintType,
    ContributionBreakdown,
    ExposureShock,
    PortfolioConstraint,
    PortfolioProposal,
    PositionIdea,
    PositionSide,
    RiskCheckStatus,
    ScenarioDefinition,
    Severity,
    StressTestResult,
    StressTestRun,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id


def build_scenario_definitions(
    *,
    portfolio_proposal: PortfolioProposal,
    clock: Clock,
    workflow_run_id: str,
) -> list[ScenarioDefinition]:
    """Build the deterministic Day 20 scenario set for one proposal."""

    now = clock.now()
    scenario_specs = [
        (
            "broad_market_drawdown",
            "Applies a uniform -10% return shock across all positions.",
            [
                _shock(
                    scope="portfolio",
                    target_identifier=None,
                    metric_name="return_shock",
                    magnitude=-0.10,
                    unit="pct_return",
                    summary="Every included position is shocked by a -10% market move.",
                )
            ],
            [
                "Applies the same directional return shock across all positions.",
                "Uses proposal target NAV and proposed weight as the only sizing inputs.",
            ],
            ["Use this to understand simple mark-to-market drawdown sensitivity."],
        ),
        (
            "sector_specific_shock",
            "Applies a -15% return shock to the proposal's dominant resolved sector when available.",
            [
                _shock(
                    scope="sector",
                    target_identifier="dominant_sector",
                    metric_name="return_shock",
                    magnitude=-0.15,
                    unit="pct_return",
                    summary="The proposal's dominant resolved sector receives a -15% shock when sector data is available.",
                )
            ],
            [
                "Requires normalized company sector metadata.",
                "Uses the dominant sector by absolute proposed weight when at least one sector resolves.",
            ],
            ["Use this to expose sector concentration that is not obvious from single-name weights alone."],
        ),
        (
            "volatility_increase",
            "Reduces the allowable stressed size to 50% of each position's max weight.",
            [
                _shock(
                    scope="constraint",
                    target_identifier="position_max_weight",
                    metric_name="stressed_position_limit_multiplier",
                    magnitude=0.50,
                    unit="multiplier",
                    summary="Each position is tested against a stressed max size equal to 50% of its configured max weight.",
                )
            ],
            [
                "This is a sizing stress, not a volatility forecast.",
                "Compares current proposed weight to a stressed allowable maximum.",
            ],
            ["Use this to identify positions that are fragile to tighter sizing assumptions."],
        ),
        (
            "concentration_breach_stress",
            "Overrides the single-name hard limit to 250 bps and checks for stressed breaches.",
            [
                _shock(
                    scope="constraint",
                    target_identifier="single_name",
                    metric_name="stressed_single_name_limit_bps",
                    magnitude=250.0,
                    unit="bps",
                    summary="Single-name sizing is retested against a tighter 250 bps hard limit.",
                )
            ],
            [
                "This is a deterministic stressed constraint override.",
                "It does not change the live proposal; it only highlights fragility under tighter concentration discipline.",
            ],
            ["Use this to expose proposals that are only acceptable under the looser base single-name limit."],
        ),
        (
            "confidence_degradation",
            "Degrades confidence by 0.25 and increases uncertainty by 0.25 for each position idea.",
            [
                _shock(
                    scope="confidence",
                    target_identifier=None,
                    metric_name="confidence_haircut",
                    magnitude=-0.25,
                    unit="score",
                    summary="Each position's confidence is reduced by 0.25.",
                ),
                _shock(
                    scope="confidence",
                    target_identifier=None,
                    metric_name="uncertainty_increase",
                    magnitude=0.25,
                    unit="score",
                    summary="Each position's uncertainty is increased by 0.25.",
                ),
            ],
            [
                "This is a structural confidence stress, not a calibrated probabilistic model.",
                "Missing confidence metadata is treated as a warning because fragility cannot be evaluated cleanly.",
            ],
            ["Use this to expose proposals that depend on optimistic confidence assumptions."],
        ),
    ]
    return [
        ScenarioDefinition(
            scenario_definition_id=make_canonical_id(
                "scenario", portfolio_proposal.portfolio_proposal_id, scenario_name
            ),
            scenario_name=scenario_name,
            description=description,
            shocks=shocks,
            assumptions=assumptions,
            review_guidance=review_guidance,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day20_scenario_definition",
                source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
                upstream_artifact_ids=[portfolio_proposal.portfolio_proposal_id],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )
        for scenario_name, description, shocks, assumptions, review_guidance in scenario_specs
    ]


def run_stress_tests(
    *,
    portfolio_proposal: PortfolioProposal,
    scenarios: list[ScenarioDefinition],
    companies_by_id: dict[str, Company],
    clock: Clock,
    workflow_run_id: str,
) -> tuple[StressTestRun, list[StressTestResult]]:
    """Run the deterministic Day 20 stress scenarios against one proposal."""

    result_builders = {
        "broad_market_drawdown": _broad_market_drawdown_result,
        "sector_specific_shock": _sector_specific_shock_result,
        "volatility_increase": _volatility_increase_result,
        "concentration_breach_stress": _concentration_breach_result,
        "confidence_degradation": _confidence_degradation_result,
    }
    run_id = make_canonical_id("stressrun", portfolio_proposal.portfolio_proposal_id)
    results = [
        result_builders[scenario.scenario_name](
            stress_test_run_id=run_id,
            portfolio_proposal=portfolio_proposal,
            scenario=scenario,
            companies_by_id=companies_by_id,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
        for scenario in scenarios
    ]
    warn_count = sum(1 for result in results if result.status is RiskCheckStatus.WARN)
    now = clock.now()
    return (
        StressTestRun(
            stress_test_run_id=run_id,
            portfolio_proposal_id=portfolio_proposal.portfolio_proposal_id,
            scenario_definition_ids=[scenario.scenario_definition_id for scenario in scenarios],
            stress_test_result_ids=[result.stress_test_result_id for result in results],
            review_required=True,
            summary=(
                f"Ran {len(scenarios)} deterministic stress scenarios; "
                f"{warn_count} produced warning-level fragility findings."
            ),
            provenance=build_provenance(
                clock=clock,
                transformation_name="day20_stress_test_run",
                source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
                upstream_artifact_ids=[
                    portfolio_proposal.portfolio_proposal_id,
                    *[scenario.scenario_definition_id for scenario in scenarios],
                ],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        ),
        results,
    )


def _broad_market_drawdown_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    companies_by_id: dict[str, Company],
    clock: Clock,
    workflow_run_id: str,
) -> StressTestResult:
    return _return_shock_result(
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal=portfolio_proposal,
        scenario=scenario,
        positions=portfolio_proposal.position_ideas,
        scenario_return=-0.10,
        companies_by_id=companies_by_id,
        clock=clock,
        workflow_run_id=workflow_run_id,
        assumptions=[
            "All positions receive the same -10% return shock.",
            "Long positions lose value under a negative return shock; short positions gain value.",
        ],
    )


def _sector_specific_shock_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    companies_by_id: dict[str, Company],
    clock: Clock,
    workflow_run_id: str,
) -> StressTestResult:
    dominant_sector = _dominant_sector(
        position_ideas=portfolio_proposal.position_ideas,
        companies_by_id=companies_by_id,
    )
    if dominant_sector is None:
        return _not_applicable_result(
            stress_test_run_id=stress_test_run_id,
            portfolio_proposal=portfolio_proposal,
            scenario=scenario,
            status=RiskCheckStatus.WARN,
            severity=Severity.MEDIUM,
            summary=(
                "Sector-specific stress could not target a dominant sector because normalized company sector metadata was unavailable."
            ),
            assumptions=[
                "Sector-specific stress requires resolved company sector metadata.",
                "No sector was inferred from ticker strings or free text.",
            ],
            workflow_run_id=workflow_run_id,
            clock=clock,
        )
    affected_positions = [
        idea
        for idea in portfolio_proposal.position_ideas
        if companies_by_id.get(idea.company_id) is not None
        and companies_by_id[idea.company_id].sector == dominant_sector
    ]
    if not affected_positions:
        return _not_applicable_result(
            stress_test_run_id=stress_test_run_id,
            portfolio_proposal=portfolio_proposal,
            scenario=scenario,
            status=RiskCheckStatus.PASS,
            severity=Severity.LOW,
            summary=(
                f"Sector-specific stress found no positions in dominant sector `{dominant_sector}` under the current proposal."
            ),
            assumptions=[
                "Dominant sector was resolved but no included position matched it under the current proposal slice."
            ],
            workflow_run_id=workflow_run_id,
            clock=clock,
        )
    return _return_shock_result(
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal=portfolio_proposal,
        scenario=scenario,
        positions=affected_positions,
        scenario_return=-0.15,
        companies_by_id=companies_by_id,
        clock=clock,
        workflow_run_id=workflow_run_id,
        assumptions=[
            f"Only positions in sector `{dominant_sector}` receive the -15% shock.",
            "Long positions lose value under a negative return shock; short positions gain value.",
        ],
    )


def _volatility_increase_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    companies_by_id: dict[str, Company],
    clock: Clock,
    workflow_run_id: str,
) -> StressTestResult:
    del companies_by_id
    stressed_rows: list[ContributionBreakdown] = []
    breached_position_ids: list[str] = []
    for idea in portfolio_proposal.position_ideas:
        stressed_max = float(idea.max_weight_bps) * 0.50
        if idea.proposed_weight_bps > stressed_max:
            breached_position_ids.append(idea.position_idea_id)
        stressed_rows.append(
            ContributionBreakdown(
                contributor_type="position_idea",
                contributor_id=idea.position_idea_id,
                metric_name="stressed_position_limit_headroom_bps",
                metric_value=stressed_max - float(idea.proposed_weight_bps),
                unit="bps",
                summary=(
                    f"Position `{idea.position_idea_id}` would face stressed headroom of {stressed_max - float(idea.proposed_weight_bps):.1f} bps "
                    f"against a stressed max of {stressed_max:.1f} bps."
                ),
            )
        )
    if not stressed_rows:
        stressed_rows.append(
            ContributionBreakdown(
                contributor_type="portfolio_proposal",
                contributor_id=portfolio_proposal.portfolio_proposal_id,
                metric_name="position_count",
                metric_value=0.0,
                unit="count",
                summary="No positions were available to test under the volatility-increase sizing stress.",
            )
        )
    status = RiskCheckStatus.WARN if breached_position_ids else RiskCheckStatus.PASS
    severity = Severity.MEDIUM if breached_position_ids else Severity.LOW
    return _build_result(
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal=portfolio_proposal,
        scenario=scenario,
        status=status,
        severity=severity,
        affected_position_ids=breached_position_ids or [idea.position_idea_id for idea in portfolio_proposal.position_ideas],
        breached_constraint_ids=[],
        estimated_pnl_impact_usd=None,
        estimated_return_impact_bps=None,
        contribution_breakdowns=stressed_rows,
        assumptions=[
            "Each position is retested against a stressed max size equal to 50% of its configured max weight.",
            "This is a sizing fragility stress, not a volatility forecast.",
        ],
        summary=(
            f"Volatility-increase sizing stress flagged {len(breached_position_ids)} positions above their stressed allowable size."
            if breached_position_ids
            else "Volatility-increase sizing stress found no positions above their stressed allowable size."
        ),
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _concentration_breach_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    companies_by_id: dict[str, Company],
    clock: Clock,
    workflow_run_id: str,
) -> StressTestResult:
    del companies_by_id
    stressed_limit = 250.0
    single_name_constraint = _constraint_by_type(
        constraints=portfolio_proposal.constraints,
        constraint_type=ConstraintType.SINGLE_NAME,
    )
    breached_positions = [
        idea for idea in portfolio_proposal.position_ideas if idea.proposed_weight_bps > stressed_limit
    ]
    contribution_breakdowns = [
        ContributionBreakdown(
            contributor_type="position_idea",
            contributor_id=idea.position_idea_id,
            metric_name="stressed_single_name_headroom_bps",
            metric_value=stressed_limit - float(idea.proposed_weight_bps),
            unit="bps",
            summary=(
                f"Position `{idea.position_idea_id}` has {stressed_limit - float(idea.proposed_weight_bps):.1f} bps of headroom under the stressed 250 bps single-name limit."
            ),
        )
        for idea in portfolio_proposal.position_ideas
    ]
    if not contribution_breakdowns:
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="portfolio_proposal",
                contributor_id=portfolio_proposal.portfolio_proposal_id,
                metric_name="position_count",
                metric_value=0.0,
                unit="count",
                summary="No positions were available for the stressed concentration test.",
            )
        )
    return _build_result(
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal=portfolio_proposal,
        scenario=scenario,
        status=RiskCheckStatus.WARN if breached_positions else RiskCheckStatus.PASS,
        severity=Severity.MEDIUM if breached_positions else Severity.LOW,
        affected_position_ids=[idea.position_idea_id for idea in breached_positions]
        or [idea.position_idea_id for idea in portfolio_proposal.position_ideas],
        breached_constraint_ids=(
            [single_name_constraint.portfolio_constraint_id]
            if breached_positions and single_name_constraint is not None
            else []
        ),
        estimated_pnl_impact_usd=None,
        estimated_return_impact_bps=None,
        contribution_breakdowns=contribution_breakdowns,
        assumptions=[
            "The base proposal is retested against a stressed 250 bps single-name limit.",
            "This does not mutate the live proposal or base constraint set.",
        ],
        summary=(
            f"Concentration stress flagged {len(breached_positions)} positions above the stressed 250 bps single-name limit."
            if breached_positions
            else "Concentration stress found no positions above the stressed 250 bps single-name limit."
        ),
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _confidence_degradation_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    companies_by_id: dict[str, Company],
    clock: Clock,
    workflow_run_id: str,
) -> StressTestResult:
    del companies_by_id
    breached_position_ids: list[str] = []
    contribution_breakdowns: list[ContributionBreakdown] = []
    for idea in portfolio_proposal.position_ideas:
        if idea.confidence is None:
            breached_position_ids.append(idea.position_idea_id)
            contribution_breakdowns.append(
                ContributionBreakdown(
                    contributor_type="position_idea",
                    contributor_id=idea.position_idea_id,
                    metric_name="missing_confidence_metadata",
                    metric_value=1.0,
                    unit="flag",
                    summary=(
                        f"Position `{idea.position_idea_id}` has no confidence metadata, so degradation fragility cannot be evaluated cleanly."
                    ),
                )
            )
            continue
        degraded_confidence = max(0.0, idea.confidence.confidence - 0.25)
        degraded_uncertainty = min(1.0, idea.confidence.uncertainty + 0.25)
        if degraded_confidence < 0.40 or degraded_uncertainty > 0.70:
            breached_position_ids.append(idea.position_idea_id)
        contribution_breakdowns.extend(
            [
                ContributionBreakdown(
                    contributor_type="position_idea",
                    contributor_id=idea.position_idea_id,
                    metric_name="degraded_confidence",
                    metric_value=degraded_confidence,
                    unit="score",
                    summary=(
                        f"Position `{idea.position_idea_id}` degrades to confidence {degraded_confidence:.2f} under the stress."
                    ),
                ),
                ContributionBreakdown(
                    contributor_type="position_idea",
                    contributor_id=idea.position_idea_id,
                    metric_name="degraded_uncertainty",
                    metric_value=degraded_uncertainty,
                    unit="score",
                    summary=(
                        f"Position `{idea.position_idea_id}` degrades to uncertainty {degraded_uncertainty:.2f} under the stress."
                    ),
                ),
            ]
        )
    if not contribution_breakdowns:
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="portfolio_proposal",
                contributor_id=portfolio_proposal.portfolio_proposal_id,
                metric_name="position_count",
                metric_value=0.0,
                unit="count",
                summary="No positions were available for confidence degradation stress.",
            )
        )
    return _build_result(
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal=portfolio_proposal,
        scenario=scenario,
        status=RiskCheckStatus.WARN if breached_position_ids else RiskCheckStatus.PASS,
        severity=Severity.MEDIUM if breached_position_ids else Severity.LOW,
        affected_position_ids=breached_position_ids
        or [idea.position_idea_id for idea in portfolio_proposal.position_ideas],
        breached_constraint_ids=[],
        estimated_pnl_impact_usd=None,
        estimated_return_impact_bps=None,
        contribution_breakdowns=contribution_breakdowns,
        assumptions=[
            "Confidence is reduced by 0.25 and uncertainty is increased by 0.25, capped to [0, 1].",
            "This is a heuristic fragility stress, not a calibrated error model.",
        ],
        summary=(
            f"Confidence degradation stress flagged {len(breached_position_ids)} positions with weak degraded confidence or missing confidence metadata."
            if breached_position_ids
            else "Confidence degradation stress found no positions crossing the degraded confidence thresholds."
        ),
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _return_shock_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    positions: list[PositionIdea],
    scenario_return: float,
    companies_by_id: dict[str, Company],
    clock: Clock,
    workflow_run_id: str,
    assumptions: list[str],
) -> StressTestResult:
    del companies_by_id
    contribution_breakdowns: list[ContributionBreakdown] = []
    total_pnl = 0.0
    for idea in positions:
        notional = portfolio_proposal.target_nav_usd * float(idea.proposed_weight_bps) / 10_000.0
        pnl_impact = notional * scenario_return
        if idea.side is PositionSide.SHORT:
            pnl_impact = -pnl_impact
        total_pnl += pnl_impact
        contribution_breakdowns.append(
            ContributionBreakdown(
                contributor_type="position_idea",
                contributor_id=idea.position_idea_id,
                metric_name="estimated_pnl_impact_usd",
                metric_value=pnl_impact,
                unit="usd",
                summary=(
                    f"Position `{idea.position_idea_id}` contributes estimated stressed PnL of {pnl_impact:.2f} USD."
                ),
            )
        )
    return_impact_bps = (
        (total_pnl / portfolio_proposal.target_nav_usd) * 10_000.0
        if portfolio_proposal.target_nav_usd > 0
        else 0.0
    )
    contribution_breakdowns.append(
        ContributionBreakdown(
            contributor_type="portfolio_proposal",
            contributor_id=portfolio_proposal.portfolio_proposal_id,
            metric_name="estimated_return_impact_bps",
            metric_value=return_impact_bps,
            unit="bps",
            summary=(
                f"Scenario `{scenario.scenario_name}` implies estimated portfolio return impact of {return_impact_bps:.1f} bps."
            ),
        )
    )
    status = RiskCheckStatus.WARN if abs(return_impact_bps) >= 25.0 else RiskCheckStatus.PASS
    severity = Severity.MEDIUM if status is RiskCheckStatus.WARN else Severity.LOW
    return _build_result(
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal=portfolio_proposal,
        scenario=scenario,
        status=status,
        severity=severity,
        affected_position_ids=[idea.position_idea_id for idea in positions],
        breached_constraint_ids=[],
        estimated_pnl_impact_usd=total_pnl,
        estimated_return_impact_bps=return_impact_bps,
        contribution_breakdowns=contribution_breakdowns,
        assumptions=assumptions,
        summary=(
            f"Scenario `{scenario.scenario_name}` produced estimated portfolio PnL impact of {total_pnl:.2f} USD ({return_impact_bps:.1f} bps)."
        ),
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _not_applicable_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    status: RiskCheckStatus,
    severity: Severity,
    summary: str,
    assumptions: list[str],
    workflow_run_id: str,
    clock: Clock,
) -> StressTestResult:
    return _build_result(
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal=portfolio_proposal,
        scenario=scenario,
        status=status,
        severity=severity,
        affected_position_ids=[],
        breached_constraint_ids=[],
        estimated_pnl_impact_usd=None,
        estimated_return_impact_bps=None,
        contribution_breakdowns=[
            ContributionBreakdown(
                contributor_type="scenario_definition",
                contributor_id=scenario.scenario_definition_id,
                metric_name="not_applicable",
                metric_value=1.0,
                unit="flag",
                summary=summary,
            )
        ],
        assumptions=assumptions,
        summary=summary,
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _build_result(
    *,
    stress_test_run_id: str,
    portfolio_proposal: PortfolioProposal,
    scenario: ScenarioDefinition,
    status: RiskCheckStatus,
    severity: Severity,
    affected_position_ids: list[str],
    breached_constraint_ids: list[str],
    estimated_pnl_impact_usd: float | None,
    estimated_return_impact_bps: float | None,
    contribution_breakdowns: list[ContributionBreakdown],
    assumptions: list[str],
    summary: str,
    clock: Clock,
    workflow_run_id: str,
) -> StressTestResult:
    now = clock.now()
    return StressTestResult(
        stress_test_result_id=make_canonical_id(
            "stressresult",
            portfolio_proposal.portfolio_proposal_id,
            scenario.scenario_name,
        ),
        stress_test_run_id=stress_test_run_id,
        portfolio_proposal_id=portfolio_proposal.portfolio_proposal_id,
        scenario_definition_id=scenario.scenario_definition_id,
        status=status,
        severity=severity,
        affected_position_ids=affected_position_ids,
        breached_constraint_ids=breached_constraint_ids,
        estimated_pnl_impact_usd=estimated_pnl_impact_usd,
        estimated_return_impact_bps=estimated_return_impact_bps,
        contribution_breakdowns=contribution_breakdowns,
        assumptions=assumptions,
        summary=summary,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day20_stress_test_result",
            source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
            upstream_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                scenario.scenario_definition_id,
                *affected_position_ids,
                *breached_constraint_ids,
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _dominant_sector(
    *,
    position_ideas: list[PositionIdea],
    companies_by_id: dict[str, Company],
) -> str | None:
    sector_totals: dict[str, int] = {}
    for idea in position_ideas:
        company = companies_by_id.get(idea.company_id)
        if company is None or not company.sector:
            continue
        sector_totals[company.sector] = sector_totals.get(company.sector, 0) + abs(
            idea.proposed_weight_bps
        )
    if not sector_totals:
        return None
    return max(sector_totals.items(), key=lambda item: item[1])[0]


def _constraint_by_type(
    *,
    constraints: list[PortfolioConstraint],
    constraint_type: ConstraintType,
) -> PortfolioConstraint | None:
    for constraint in constraints:
        if constraint.constraint_type is constraint_type:
            return constraint
    return None


def _shock(
    *,
    scope: str,
    target_identifier: str | None,
    metric_name: str,
    magnitude: float,
    unit: str,
    summary: str,
) -> ExposureShock:
    return ExposureShock(
        shock_scope=scope,
        target_identifier=target_identifier,
        metric_name=metric_name,
        magnitude=magnitude,
        unit=unit,
        summary=summary,
    )
