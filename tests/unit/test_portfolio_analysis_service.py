from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    Company,
    ConfidenceAssessment,
    ConstraintType,
    DerivedArtifactValidationStatus,
    FeatureFamily,
    PortfolioConstraint,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    ResearchStance,
    Signal,
    SignalLineage,
    SignalStatus,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.time import FrozenClock
from services.portfolio_analysis import PortfolioAnalysisService
from services.portfolio_analysis.stress import build_scenario_definitions, run_stress_tests

FIXED_NOW = datetime(2026, 3, 20, 13, 0, tzinfo=UTC)
PROVENANCE = ProvenanceRecord(
    source_reference_ids=["src_apex"],
    upstream_artifact_ids=[],
    processing_time=FIXED_NOW,
)


def test_portfolio_analysis_service_persists_linked_artifacts(tmp_path: Path) -> None:
    proposal, signals_by_id, companies_by_id = _build_sample_inputs()
    service = PortfolioAnalysisService(clock=FrozenClock(FIXED_NOW))

    response = service.analyze_portfolio_proposal(
        portfolio_proposal=proposal,
        signals_by_id=signals_by_id,
        companies_by_id=companies_by_id,
        output_root=tmp_path / "portfolio_analysis",
        requested_by="unit_test",
    )

    assert response.portfolio_attribution.portfolio_proposal_id == proposal.portfolio_proposal_id
    assert len(response.position_attributions) == 2
    assert response.stress_test_run.portfolio_proposal_id == proposal.portfolio_proposal_id
    assert len(response.stress_test_results) == 5
    assert response.storage_locations
    assert all(location.uri.startswith("file://") for location in response.storage_locations)


def test_broad_market_drawdown_handles_long_and_short_pnl_math() -> None:
    proposal, _, companies_by_id = _build_sample_inputs()
    scenarios = build_scenario_definitions(
        portfolio_proposal=proposal,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="day20_test",
    )

    _, results = run_stress_tests(
        portfolio_proposal=proposal,
        scenarios=scenarios,
        companies_by_id=companies_by_id,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="day20_test",
    )

    broad_result = next(
        result for result in results if result.summary.startswith("Scenario `broad_market_drawdown`")
    )
    assert broad_result.estimated_pnl_impact_usd == -2000.0
    assert broad_result.estimated_return_impact_bps == -20.0


def test_sector_shock_warns_honestly_when_sector_metadata_is_missing() -> None:
    proposal, _, _ = _build_sample_inputs()
    scenarios = build_scenario_definitions(
        portfolio_proposal=proposal,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="day20_test",
    )

    _, results = run_stress_tests(
        portfolio_proposal=proposal,
        scenarios=scenarios,
        companies_by_id={},
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="day20_test",
    )
    sector_scenario_id = next(
        scenario.scenario_definition_id
        for scenario in scenarios
        if scenario.scenario_name == "sector_specific_shock"
    )

    sector_result = next(
        result for result in results if result.scenario_definition_id == sector_scenario_id
    )
    assert sector_result.status.value == "warn"
    assert "sector metadata was unavailable" in sector_result.summary


def test_confidence_degradation_warns_on_missing_confidence(tmp_path: Path) -> None:
    proposal, signals_by_id, companies_by_id = _build_sample_inputs()
    proposal = proposal.model_copy(
        update={
            "position_ideas": [
                proposal.position_ideas[0],
                proposal.position_ideas[1].model_copy(update={"confidence": None}),
            ]
        }
    )
    service = PortfolioAnalysisService(clock=FrozenClock(FIXED_NOW))

    response = service.analyze_portfolio_proposal(
        portfolio_proposal=proposal,
        signals_by_id=signals_by_id,
        companies_by_id=companies_by_id,
        output_root=tmp_path / "portfolio_analysis",
        requested_by="unit_test",
    )
    confidence_scenario_id = next(
        scenario.scenario_definition_id
        for scenario in response.scenario_definitions
        if scenario.scenario_name == "confidence_degradation"
    )

    confidence_result = next(
        result
        for result in response.stress_test_results
        if result.scenario_definition_id == confidence_scenario_id
    )
    assert confidence_result.status.value == "warn"
    assert any(
        breakdown.metric_name == "missing_confidence_metadata"
        for breakdown in confidence_result.contribution_breakdowns
    )


def _build_sample_inputs() -> tuple[PortfolioProposal, dict[str, Signal], dict[str, Company]]:
    signal_long = _signal(
        signal_id="signal_long",
        company_id="co_apex",
        stance=ResearchStance.POSITIVE,
        score=0.8,
    )
    signal_short = _signal(
        signal_id="signal_short",
        company_id="co_beta",
        stance=ResearchStance.NEGATIVE,
        score=-0.6,
    )
    idea_long = _position_idea(
        position_idea_id="idea_long",
        company_id="co_apex",
        signal_id=signal_long.signal_id,
        symbol="APEX",
        side=PositionSide.LONG,
        proposed_weight_bps=400,
        confidence=ConfidenceAssessment(confidence=0.70, uncertainty=0.30),
    )
    idea_short = _position_idea(
        position_idea_id="idea_short",
        company_id="co_beta",
        signal_id=signal_short.signal_id,
        symbol="BETA",
        side=PositionSide.SHORT,
        proposed_weight_bps=200,
        confidence=ConfidenceAssessment(confidence=0.65, uncertainty=0.35),
    )
    constraints = [
        PortfolioConstraint(
            portfolio_constraint_id="constraint_single_name",
            constraint_type=ConstraintType.SINGLE_NAME,
            scope="single_name",
            hard_limit=500.0,
            soft_limit=None,
            unit="bps",
            description="No single name above 500 bps.",
            active=True,
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        PortfolioConstraint(
            portfolio_constraint_id="constraint_gross",
            constraint_type=ConstraintType.GROSS_EXPOSURE,
            scope="portfolio",
            hard_limit=1500.0,
            soft_limit=None,
            unit="bps",
            description="Gross exposure cap.",
            active=True,
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        PortfolioConstraint(
            portfolio_constraint_id="constraint_net",
            constraint_type=ConstraintType.NET_EXPOSURE,
            scope="portfolio",
            hard_limit=1000.0,
            soft_limit=None,
            unit="bps",
            description="Net exposure cap.",
            active=True,
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        PortfolioConstraint(
            portfolio_constraint_id="constraint_turnover",
            constraint_type=ConstraintType.TURNOVER,
            scope="portfolio",
            hard_limit=1500.0,
            soft_limit=None,
            unit="bps",
            description="Turnover cap.",
            active=True,
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
    ]
    proposal = PortfolioProposal(
        portfolio_proposal_id="proposal_1",
        name="sample_portfolio",
        as_of_time=FIXED_NOW,
        generated_at=FIXED_NOW,
        target_nav_usd=1_000_000.0,
        position_ideas=[idea_long, idea_short],
        constraints=constraints,
        risk_checks=[],
        exposure_summary=PortfolioExposureSummary(
            portfolio_exposure_summary_id="pexpo_1",
            gross_exposure_bps=600,
            net_exposure_bps=200,
            long_exposure_bps=400,
            short_exposure_bps=200,
            cash_buffer_bps=9400,
            position_count=2,
            turnover_bps_assumption=600,
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        blocking_issues=[],
        review_decision_ids=[],
        signal_bundle_id=None,
        arbitration_decision_id=None,
        portfolio_attribution_id=None,
        stress_test_run_id=None,
        review_required=True,
        status=PortfolioProposalStatus.PENDING_REVIEW,
        summary="Two-position sample proposal.",
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    companies_by_id = {
        "co_apex": Company(
            company_id="co_apex",
            legal_name="Apex Holdings",
            ticker="APEX",
            sector="Technology",
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        "co_beta": Company(
            company_id="co_beta",
            legal_name="Beta Industrial",
            ticker="BETA",
            sector="Industrials",
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
    }
    return proposal, {signal_long.signal_id: signal_long, signal_short.signal_id: signal_short}, companies_by_id


def _signal(*, signal_id: str, company_id: str, stance: ResearchStance, score: float) -> Signal:
    return Signal(
        signal_id=signal_id,
        company_id=company_id,
        hypothesis_id=f"hyp_{signal_id}",
        signal_family="text_signal",
        stance=stance,
        ablation_view=AblationView.TEXT_ONLY,
        thesis_summary=f"{signal_id} thesis",
        feature_ids=[f"feature_{signal_id}"],
        component_scores=[],
        primary_score=score,
        effective_at=FIXED_NOW,
        status=SignalStatus.CANDIDATE,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        lineage=SignalLineage(
            signal_lineage_id=f"lineage_{signal_id}",
            feature_ids=[f"feature_{signal_id}"],
            feature_definition_ids=[f"featuredef_{signal_id}"],
            feature_value_ids=[f"featureval_{signal_id}"],
            research_artifact_ids=[f"hyp_{signal_id}"],
            supporting_evidence_link_ids=[f"sel_{signal_id}"],
            input_families=[FeatureFamily.TEXT_DERIVED],
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        assumptions=[],
        uncertainties=[],
        confidence=ConfidenceAssessment(confidence=0.7, uncertainty=0.3),
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _position_idea(
    *,
    position_idea_id: str,
    company_id: str,
    signal_id: str,
    symbol: str,
    side: PositionSide,
    proposed_weight_bps: int,
    confidence: ConfidenceAssessment | None,
) -> PositionIdea:
    return PositionIdea(
        position_idea_id=position_idea_id,
        company_id=company_id,
        signal_id=signal_id,
        symbol=symbol,
        instrument_type="equity",
        side=side,
        thesis_summary=f"{position_idea_id} thesis",
        selection_reason="Selected for deterministic testing.",
        entry_conditions=["human review complete"],
        exit_conditions=["signal flips"],
        target_horizon="next_1_4_quarters",
        proposed_weight_bps=proposed_weight_bps,
        max_weight_bps=500,
        evidence_span_ids=[f"evidence_{position_idea_id}"],
        supporting_evidence_link_ids=[f"sel_{position_idea_id}"],
        research_artifact_ids=[f"hyp_{signal_id}"],
        review_decision_ids=[],
        signal_bundle_id=None,
        arbitration_decision_id=None,
        status=PositionIdeaStatus.PENDING_REVIEW,
        confidence=confidence,
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
