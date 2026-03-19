from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pytest import CaptureFixture

from pipelines.demo.end_to_end_demo import (
    DEFAULT_FIXTURES_ROOT,
    DEFAULT_PRICE_FIXTURE_PATH,
    main,
    run_end_to_end_demo,
)

FIXED_NOW = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


def test_end_to_end_demo_runs_full_stack_and_persists_manifest(tmp_path: Path) -> None:
    response = run_end_to_end_demo(
        fixtures_root=DEFAULT_FIXTURES_ROOT,
        price_fixture_path=DEFAULT_PRICE_FIXTURE_PATH,
        base_root=tmp_path / "demo_run",
        requested_by="integration_test",
        frozen_time=FIXED_NOW,
    )

    assert response.manifest_path.exists()
    assert response.ingestion
    assert response.evidence_extraction
    assert response.research.research_brief is not None
    assert response.feature_signal.feature_mapping.features
    assert response.feature_signal.signal_generation.signals
    assert response.backtest.backtest_run.backtest_run_id
    assert response.ablation.ablation_result.ablation_result_id
    assert response.ablation.evaluation_report is not None
    assert response.portfolio_review.final_portfolio_proposal.portfolio_proposal_id
    assert response.portfolio_review.paper_trades
    assert response.review_queue.queue_items
    assert response.review_note.review_note.review_note_id
    assert response.review_action.review_decision.review_decision_id
    assert (response.base_root / "audit" / "audit_logs").exists()

    workflow_names = {summary.workflow_name for summary in response.recent_run_summaries.items}
    assert {
        "fixture_ingestion",
        "evidence_extraction",
        "research_workflow",
        "feature_mapping",
        "signal_generation",
        "strategy_ablation",
        "portfolio_review_pipeline",
        "review_action",
    }.issubset(workflow_names)

    assert response.health_checks.health_checks
    assert all(
        forbidden not in "\n".join(response.notes).lower()
        for forbidden in ["proves alpha", "validated alpha", "live trading enabled", "guaranteed edge"]
    )


def test_end_to_end_demo_cli_smoke(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "--fixtures-root",
            str(DEFAULT_FIXTURES_ROOT),
            "--price-fixture-path",
            str(DEFAULT_PRICE_FIXTURE_PATH),
            "--base-root",
            str(tmp_path / "cli_demo"),
            "--requested-by",
            "cli_smoke_test",
            "--frozen-time",
            "2026-04-01T12:00:00Z",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "manifest_path=" in captured.out
    manifest_line = next(
        line for line in captured.out.splitlines() if line.startswith("manifest_path=")
    )
    manifest_path = Path(manifest_line.split("=", 1)[1].strip())
    assert manifest_path.exists()
