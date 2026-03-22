from __future__ import annotations

from datetime import UTC, datetime

import pytest

from libraries.schemas import (
    ContributionBreakdown,
    ExposureShock,
    PortfolioAttribution,
    PositionAttribution,
    ScenarioDefinition,
    StressTestResult,
    StressTestRun,
)
from libraries.schemas.base import ProvenanceRecord, RiskCheckStatus, Severity

FIXED_NOW = datetime(2026, 3, 20, 13, 0, tzinfo=UTC)
PROVENANCE = ProvenanceRecord(processing_time=FIXED_NOW)


def test_position_attribution_requires_breakdowns() -> None:
    with pytest.raises(ValueError, match="contribution_breakdowns"):
        PositionAttribution(
            position_attribution_id="posattr_1",
            portfolio_proposal_id="proposal_1",
            position_idea_id="idea_1",
            company_id="co_apex",
            signal_id="signal_1",
            portfolio_constraint_ids=["constraint_1"],
            supporting_evidence_link_ids=["sel_1"],
            from_arbitrated_signal=False,
            contribution_breakdowns=[],
            summary="Missing breakdowns should be rejected.",
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_scenario_definition_requires_explicit_shocks() -> None:
    with pytest.raises(ValueError, match="shocks must contain at least one explicit shock"):
        ScenarioDefinition(
            scenario_definition_id="scenario_1",
            scenario_name="broad_market_drawdown",
            description="No shocks present.",
            shocks=[],
            assumptions=[],
            review_guidance=[],
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_stress_test_result_requires_summary_and_breakdowns() -> None:
    with pytest.raises(ValueError, match="contribution_breakdowns"):
        StressTestResult(
            stress_test_result_id="stress_1",
            stress_test_run_id="stressrun_1",
            portfolio_proposal_id="proposal_1",
            scenario_definition_id="scenario_1",
            status=RiskCheckStatus.WARN,
            severity=Severity.MEDIUM,
            affected_position_ids=["idea_1"],
            breached_constraint_ids=[],
            estimated_pnl_impact_usd=-1200.0,
            estimated_return_impact_bps=-12.0,
            contribution_breakdowns=[],
            assumptions=["heuristic"],
            summary="Missing breakdowns should be rejected.",
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_valid_portfolio_analysis_schema_objects_round_trip() -> None:
    breakdown = ContributionBreakdown(
        contributor_type="position_idea",
        contributor_id="idea_1",
        metric_name="proposed_weight_bps",
        metric_value=300.0,
        unit="bps",
        summary="Position contributes 300 bps.",
    )
    position_attribution = PositionAttribution(
        position_attribution_id="posattr_1",
        portfolio_proposal_id="proposal_1",
        position_idea_id="idea_1",
        company_id="co_apex",
        signal_id="signal_1",
        portfolio_constraint_ids=["constraint_1"],
        supporting_evidence_link_ids=["sel_1"],
        from_arbitrated_signal=True,
        contribution_breakdowns=[breakdown],
        summary="Position attribution is explicit.",
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    portfolio_attribution = PortfolioAttribution(
        portfolio_attribution_id="portattr_1",
        portfolio_proposal_id="proposal_1",
        position_attribution_ids=[position_attribution.position_attribution_id],
        signal_ids=["signal_1"],
        portfolio_constraint_ids=["constraint_1"],
        dominant_position_idea_ids=["idea_1"],
        contribution_breakdowns=[breakdown],
        concentration_summary="Top position drives concentration.",
        exposure_summary="Gross 300 bps, net 300 bps.",
        summary="Portfolio attribution is explicit.",
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    scenario = ScenarioDefinition(
        scenario_definition_id="scenario_1",
        scenario_name="confidence_degradation",
        description="Degrade confidence explicitly.",
        shocks=[
            ExposureShock(
                shock_scope="confidence",
                target_identifier=None,
                metric_name="confidence_haircut",
                magnitude=-0.25,
                unit="score",
                summary="Reduce confidence by 0.25.",
            )
        ],
        assumptions=["heuristic only"],
        review_guidance=["inspect missing confidence carefully"],
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    stress_result = StressTestResult(
        stress_test_result_id="stress_1",
        stress_test_run_id="stressrun_1",
        portfolio_proposal_id="proposal_1",
        scenario_definition_id=scenario.scenario_definition_id,
        status=RiskCheckStatus.WARN,
        severity=Severity.MEDIUM,
        affected_position_ids=["idea_1"],
        breached_constraint_ids=[],
        estimated_pnl_impact_usd=None,
        estimated_return_impact_bps=None,
        contribution_breakdowns=[breakdown],
        assumptions=["heuristic only"],
        summary="Confidence degradation created a warning.",
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    stress_run = StressTestRun(
        stress_test_run_id="stressrun_1",
        portfolio_proposal_id="proposal_1",
        scenario_definition_ids=[scenario.scenario_definition_id],
        stress_test_result_ids=[stress_result.stress_test_result_id],
        review_required=True,
        summary="Ran one stress scenario.",
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert portfolio_attribution.portfolio_proposal_id == "proposal_1"
    assert stress_run.stress_test_result_ids == ["stress_1"]
