from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
    ExperimentArtifact,
    ReviewOutcome,
    Severity,
    SignalStatus,
)
from libraries.schemas.base import ProvenanceRecord
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

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)


def test_portfolio_review_pipeline_persists_reviewable_portfolio_artifacts(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"

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

    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        assumed_reference_prices={"APEX": 103.0},
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.final_position_ideas
    assert response.final_portfolio_proposal.risk_checks
    assert response.paper_trades == []
    assert response.strategy_to_paper_mapping is not None
    assert response.reconciliation_report is not None
    assert response.realism_warnings
    assert response.constraint_set is not None
    assert response.construction_decisions
    assert response.position_sizing_rationales
    assert response.portfolio_selection_summary is not None
    assert response.final_portfolio_proposal.strategy_to_paper_mapping_id == (
        response.strategy_to_paper_mapping.strategy_to_paper_mapping_id
    )
    assert response.final_portfolio_proposal.reconciliation_report_id == (
        response.reconciliation_report.reconciliation_report_id
    )
    assert response.final_portfolio_proposal.portfolio_selection_summary_id == (
        response.portfolio_selection_summary.portfolio_selection_summary_id
    )

    position_idea = response.final_position_ideas[0]
    proposal = response.final_portfolio_proposal

    position_idea_path = (
        artifact_root / "portfolio" / "position_ideas" / f"{position_idea.position_idea_id}.json"
    )
    proposal_path = (
        artifact_root
        / "portfolio"
        / "portfolio_proposals"
        / f"{proposal.portfolio_proposal_id}.json"
    )
    audit_directory = artifact_root / "audit" / "audit_logs"
    reconciliation_report_path = (
        artifact_root
        / "reconciliation"
        / "reconciliation_reports"
        / f"{response.reconciliation_report.reconciliation_report_id}.json"
    )
    selection_summary_path = (
        artifact_root
        / "portfolio"
        / "portfolio_selection_summaries"
        / f"{response.portfolio_selection_summary.portfolio_selection_summary_id}.json"
    )
    assert position_idea_path.exists()
    assert proposal_path.exists()
    assert audit_directory.exists()
    assert reconciliation_report_path.exists()
    assert selection_summary_path.exists()

    position_payload = json.loads(position_idea_path.read_text(encoding="utf-8"))
    proposal_payload = json.loads(proposal_path.read_text(encoding="utf-8"))
    audit_event_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(audit_directory.glob("*.json"))
    ]

    signal_payload = json.loads(
        next((artifact_root / "signal_generation" / "signals").glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert position_payload["signal_id"] == signal_payload["signal_id"]
    assert set(position_payload["supporting_evidence_link_ids"]) == set(
        signal_payload["lineage"]["supporting_evidence_link_ids"]
    )
    assert proposal_payload["exposure_summary"]["position_count"] == len(
        proposal_payload["position_ideas"]
    )
    assert proposal_payload["risk_checks"]
    assert {
        "research_workflow_completed",
        "feature_mapping_completed",
        "signal_generation_completed",
        "backtest_workflow_completed",
        "portfolio_review_pipeline_completed",
    }.issubset({payload["event_type"] for payload in audit_event_payloads})


def test_portfolio_review_pipeline_creates_paper_trades_only_after_explicit_approval(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"

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

    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_test",
        review_notes=["Approved for paper-trade candidate creation."],
        assumed_reference_prices={"APEX": 103.0},
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.paper_trades
    assert response.strategy_to_paper_mapping is not None
    assert response.reconciliation_report is not None
    assert response.assumption_mismatches
    assert response.realism_warnings
    assert response.portfolio_selection_summary is not None
    paper_trade = response.paper_trades[0]
    paper_trade_path = (
        artifact_root / "portfolio" / "paper_trades" / f"{paper_trade.paper_trade_id}.json"
    )
    reconciliation_report_path = (
        artifact_root
        / "reconciliation"
        / "reconciliation_reports"
        / f"{response.reconciliation_report.reconciliation_report_id}.json"
    )
    assert paper_trade_path.exists()
    assert reconciliation_report_path.exists()

    paper_trade_payload = json.loads(paper_trade_path.read_text(encoding="utf-8"))
    assert paper_trade_payload["portfolio_proposal_id"] == response.final_portfolio_proposal.portfolio_proposal_id
    assert paper_trade_payload["execution_mode"] == "paper_only"
    assert paper_trade_payload["execution_timing_rule_id"] is not None
    assert paper_trade_payload["fill_assumption_id"] is not None
    assert paper_trade_payload["cost_model_id"] is not None
    assert "live" not in "".join(paper_trade_payload["execution_notes"]).lower().replace(
        "no live routing", ""
    )
    experiment_artifacts = [
        ExperimentArtifact.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((artifact_root / "experiments" / "experiment_artifacts").glob("*.json"))
    ]
    assert "ReconciliationReport" in {
        artifact.artifact_type for artifact in experiment_artifacts
    }


def test_portfolio_review_pipeline_surfaces_high_severity_reconciliation_attention(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"

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

    response = run_portfolio_review_pipeline(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=artifact_root / "backtesting",
        output_root=artifact_root / "portfolio",
        proposal_review_outcome=ReviewOutcome.APPROVE,
        reviewer_id="pm_test",
        review_notes=["Approved for paper-trade candidate creation."],
        assumed_reference_prices={"APEX": 103.0},
        clock=FrozenClock(datetime(2026, 3, 17, 7, 0, tzinfo=UTC)),
    )

    assert response.reconciliation_report is not None
    assert response.reconciliation_report.highest_severity in {Severity.HIGH, Severity.CRITICAL}
    monitoring_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((artifact_root / "monitoring" / "run_summaries").glob("*.json"))
    ]
    assert any(
        payload["workflow_name"] == "portfolio_review_pipeline"
        and "reconciliation_high_severity_mismatch" in payload["attention_reasons"]
        for payload in monitoring_payloads
    )


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
