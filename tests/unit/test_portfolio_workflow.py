from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ConstraintResult,
    DerivedArtifactValidationStatus,
    ExecutionAssumption,
    PortfolioConstraint,
    ReviewOutcome,
    Signal,
    SignalStatus,
)
from libraries.schemas.base import ConstraintType, ProvenanceRecord
from libraries.time import FrozenClock
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_backtest_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.signal_generation import run_feature_signal_pipeline
from services.portfolio import PortfolioConstructionService, RunPortfolioWorkflowRequest
from services.risk_engine.rules import evaluate_portfolio_risk

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_candidate_signal_creates_300bps_position_and_review_bound_proposal(
    tmp_path: Path,
) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")

    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        assumed_reference_prices={"APEX": 102.0},
        clock=FrozenClock(FIXED_NOW),
    )

    assert len(response.final_position_ideas) == 1
    assert response.final_position_ideas[0].proposed_weight_bps == 300
    assert response.final_position_ideas[0].signal_bundle_id is not None
    assert response.final_position_ideas[0].arbitration_decision_id is not None
    assert "arbitrated primary signal" in response.final_position_ideas[0].selection_reason
    assert response.final_portfolio_proposal.status.value == "pending_review"
    assert response.final_portfolio_proposal.signal_bundle_id is not None
    assert response.final_portfolio_proposal.arbitration_decision_id is not None
    assert response.portfolio_workflow.portfolio_attribution is not None
    assert response.portfolio_workflow.stress_test_run is not None
    assert response.portfolio_workflow.position_attributions
    assert response.portfolio_workflow.stress_test_results
    assert response.portfolio_workflow.constraint_set is not None
    assert response.portfolio_workflow.construction_decisions
    assert response.portfolio_workflow.position_sizing_rationales
    assert response.portfolio_workflow.portfolio_selection_summary is not None
    assert (
        response.final_portfolio_proposal.portfolio_attribution_id
        == response.portfolio_workflow.portfolio_attribution.portfolio_attribution_id
    )
    assert (
        response.final_portfolio_proposal.stress_test_run_id
        == response.portfolio_workflow.stress_test_run.stress_test_run_id
    )
    assert (
        response.final_portfolio_proposal.portfolio_selection_summary_id
        == response.portfolio_workflow.portfolio_selection_summary.portfolio_selection_summary_id
    )
    assert response.final_position_ideas[0].construction_decision_id is not None
    assert response.final_position_ideas[0].position_sizing_rationale_id is not None
    assert response.paper_trades == []
    assert any("zero paper-trade candidates were created" in note for note in response.notes)
    assert any("proposal_status=pending_review" in note for note in response.notes)
    assert any("not replay-safe" in note for note in response.portfolio_workflow.notes)
    assert any("portfolio_analysis" in location.uri for location in response.storage_locations)
    assert {
        "portfolio_concentration_fragility",
        "portfolio_stress_fragility",
    }.issubset({check.rule_name for check in response.risk_checks})


def test_approved_validated_signal_creates_500bps_position(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    payload = json.loads(signal_path.read_text(encoding="utf-8"))
    payload["status"] = SignalStatus.APPROVED.value
    payload["validation_status"] = DerivedArtifactValidationStatus.VALIDATED.value
    signal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    service = PortfolioConstructionService(clock=FrozenClock(FIXED_NOW))
    response = service.run_portfolio_workflow(
        RunPortfolioWorkflowRequest(
            signal_root=artifact_root / "signal_generation",
            research_root=artifact_root / "research",
            ingestion_root=artifact_root / "ingestion",
            backtesting_root=artifact_root / "backtesting",
            output_root=artifact_root / "portfolio",
            requested_by="unit_test",
        )
    )

    assert len(response.position_ideas) == 1
    assert response.position_ideas[0].proposed_weight_bps == 500
    assert "Selected from raw signal" in response.position_ideas[0].selection_reason
    assert response.portfolio_attribution is not None
    assert response.stress_test_run is not None
    assert any("temporary raw-signal fallback" in note for note in response.notes)


def test_same_company_multi_signal_case_records_inclusion_and_rejection_decisions(
    tmp_path: Path,
) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    signal = Signal.model_validate_json(signal_path.read_text(encoding="utf-8"))
    competing_signal = signal.model_copy(
        update={
            "signal_id": make_canonical_id("signal", "competing", signal.company_id),
            "signal_family": "competing_text_only_candidate_signal",
            "primary_score": signal.primary_score - 0.15,
            "created_at": signal.created_at,
            "updated_at": signal.updated_at,
        }
    )
    competing_signal_path = (
        artifact_root / "signal_generation" / "signals" / f"{competing_signal.signal_id}.json"
    )
    competing_signal_path.write_text(
        competing_signal.model_dump_json(indent=2),
        encoding="utf-8",
    )

    response = PortfolioConstructionService(clock=FrozenClock(FIXED_NOW)).run_portfolio_workflow(
        RunPortfolioWorkflowRequest(
            signal_root=artifact_root / "signal_generation",
            signal_arbitration_root=artifact_root / "missing_signal_arbitration",
            research_root=artifact_root / "research",
            ingestion_root=artifact_root / "ingestion",
            backtesting_root=artifact_root / "backtesting",
            output_root=artifact_root / "portfolio",
            requested_by="unit_test",
        )
    )

    assert len(response.position_ideas) == 1
    assert response.selection_conflicts
    assert response.portfolio_selection_summary is not None
    assert len(response.construction_decisions) == 2
    included_decision = next(
        decision
        for decision in response.construction_decisions
        if decision.decision_outcome == "included"
    )
    rejected_decision = next(
        decision
        for decision in response.construction_decisions
        if decision.decision_outcome == "rejected"
    )
    assert included_decision.position_idea_id == response.position_ideas[0].position_idea_id
    assert rejected_decision.proposal_rejection_reasons[0].reason_code in {
        "lower_ranked_same_company_candidate",
        "portfolio_constraint_breach",
    }
    assert response.portfolio_selection_summary.rejected_signal_ids == [rejected_decision.signal_id]


def test_single_name_cap_creates_binding_constraint_result_and_sizing_rationale(
    tmp_path: Path,
) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    payload = json.loads(signal_path.read_text(encoding="utf-8"))
    payload["status"] = SignalStatus.APPROVED.value
    payload["validation_status"] = DerivedArtifactValidationStatus.VALIDATED.value
    signal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    single_name_constraint = PortfolioConstraint(
        portfolio_constraint_id="constraint_single_name_cap_test",
        constraint_type=ConstraintType.SINGLE_NAME,
        scope="single_name",
        hard_limit=200.0,
        soft_limit=None,
        unit="bps",
        description="Artificially low single-name limit for unit testing.",
        active=True,
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    response = PortfolioConstructionService(clock=FrozenClock(FIXED_NOW)).run_portfolio_workflow(
        RunPortfolioWorkflowRequest(
            signal_root=artifact_root / "signal_generation",
            signal_arbitration_root=artifact_root / "missing_signal_arbitration",
            research_root=artifact_root / "research",
            ingestion_root=artifact_root / "ingestion",
            backtesting_root=artifact_root / "backtesting",
            output_root=artifact_root / "portfolio",
            constraints=[single_name_constraint],
            requested_by="unit_test",
        )
    )

    assert response.position_ideas[0].proposed_weight_bps == 200
    assert response.position_sizing_rationales[0].final_weight_bps == 200
    binding_result = next(
        result
        for result in response.constraint_results
        if isinstance(result, ConstraintResult)
        and result.portfolio_constraint_id == single_name_constraint.portfolio_constraint_id
        and result.subject_type == "candidate_signal"
    )
    assert binding_result.binding is True


def test_monitor_signal_does_not_create_position_ideas(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    signal_path = next((artifact_root / "signal_generation" / "signals").glob("*.json"))
    payload = json.loads(signal_path.read_text(encoding="utf-8"))
    payload["stance"] = "monitor"
    signal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.final_position_ideas == []
    assert response.paper_trades == []


def test_missing_rationale_creates_blocking_risk_failure(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    workflow = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        clock=FrozenClock(FIXED_NOW),
    )
    broken_idea = workflow.final_position_ideas[0].model_copy(update={"selection_reason": ""})

    signal = Signal.model_validate_json(
        next((artifact_root / "signal_generation" / "signals").glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    result = evaluate_portfolio_risk(
        position_ideas=[broken_idea],
        portfolio_proposal=workflow.final_portfolio_proposal.model_copy(
            update={"position_ideas": [broken_idea]}
        ),
        constraints=workflow.final_portfolio_proposal.constraints,
        signals_by_id={broken_idea.signal_id: signal},
        evidence_assessments_by_id={},
        signal_bundle=None,
        arbitration_decision=None,
        signal_conflicts=[],
        constraint_set=None,
        constraint_results=[],
        position_sizing_rationales=[],
        construction_decisions=[],
        selection_conflicts=[],
        portfolio_selection_summary=None,
        portfolio_attribution=None,
        stress_test_run=None,
        stress_test_results=[],
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="riskeval_test",
    )

    assert any(check.blocking for check in result.risk_checks)


def test_exposure_breach_blocks_paper_trades(tmp_path: Path) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")
    constraint = PortfolioConstraint(
        portfolio_constraint_id="constraint_gross_test",
        constraint_type=ConstraintType.GROSS_EXPOSURE,
        scope="portfolio",
        hard_limit=200.0,
        soft_limit=None,
        unit="bps",
        description="Artificially low gross limit for unit testing.",
        active=True,
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        constraints=[constraint],
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.final_position_ideas == []
    assert response.portfolio_selection_summary is not None
    rejected_decision = next(
        decision
        for decision in response.construction_decisions
        if decision.decision_outcome == "rejected"
    )
    assert rejected_decision.proposal_rejection_reasons[0].reason_code == "portfolio_constraint_breach"
    assert response.paper_trades == []


def test_review_outcome_updates_portfolio_status_without_autoapproving_trades(
    tmp_path: Path,
) -> None:
    artifact_root = _build_full_stack(artifact_root=tmp_path / "artifacts")

    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_test",
        review_notes=["Approved for paper-trade candidate creation."],
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.review_decision is not None
    assert response.final_portfolio_proposal.status.value == "approved"
    assert response.paper_trades
    assert all(trade.status.value == "proposed" for trade in response.paper_trades)


def _build_full_stack(*, artifact_root: Path) -> Path:
    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=artifact_root / "ingestion",
        clock=FrozenClock(FIXED_NOW),
    )
    run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=FrozenClock(FIXED_NOW),
    )
    run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(FIXED_NOW),
    )
    run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(FIXED_NOW),
    )
    run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )
    return artifact_root


def _backtest_config() -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id(
            "btcfg",
            "text_only_candidate_signal",
            "2026-03-17",
            "2026-03-30",
            "5.0",
            "2.0",
        ),
        strategy_name="day6_text_signal_exploratory",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", "5.0", "2.0", "lag1"),
            transaction_cost_bps=5.0,
            slippage_bps=2.0,
            execution_lag_bars=1,
            decision_price_field="close",
            execution_price_field="open",
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
