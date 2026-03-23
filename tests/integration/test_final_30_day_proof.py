from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pytest import CaptureFixture

from pipelines.demo.end_to_end_demo import DEFAULT_FIXTURES_ROOT, DEFAULT_PRICE_FIXTURE_PATH
from pipelines.demo.final_30_day_proof import main, run_final_30_day_proof

FIXED_NOW = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


def test_final_30_day_proof_runs_review_bound_demo_and_approved_appendix(
    tmp_path: Path,
) -> None:
    response = run_final_30_day_proof(
        fixtures_root=DEFAULT_FIXTURES_ROOT,
        price_fixture_path=DEFAULT_PRICE_FIXTURE_PATH,
        base_root=tmp_path / "final_proof",
        requested_by="integration_test",
        frozen_time=FIXED_NOW,
    )

    assert response.manifest_path.exists()
    assert response.review_bound_branch.demo_manifest_path.exists()
    assert response.review_bound_branch.ingestion_document_ids
    assert response.review_bound_branch.evidence_bundle_document_ids
    assert response.review_bound_branch.evidence_assessment_id
    assert response.review_bound_branch.feature_ids
    assert response.review_bound_branch.signal_ids
    assert response.review_bound_branch.backtest_run_id
    assert response.review_bound_branch.ablation_result_id
    assert response.review_bound_branch.portfolio_proposal_id
    assert response.review_bound_branch.risk_summary_id is not None
    assert response.review_bound_branch.proposal_scorecard_id is not None
    assert response.review_bound_branch.review_queue_item_ids
    assert response.review_bound_branch.review_decision_ids
    assert response.review_bound_branch.run_summary_ids
    assert response.review_bound_branch.audit_log_ids
    assert "paper_trade_stop_kind=review_bound" in response.review_bound_branch.notes

    assert response.approved_appendix.approved_proposal_id
    assert response.approved_appendix.proposal_review_decision_id is not None
    assert response.approved_appendix.paper_trade_id
    assert response.approved_appendix.paper_trade_review_decision_id
    assert response.approved_appendix.paper_position_state_id
    assert len(response.approved_appendix.lifecycle_event_ids) >= 3
    assert response.approved_appendix.trade_outcome_id
    assert response.approved_appendix.outcome_attribution_id
    assert response.approved_appendix.daily_paper_summary_id
    assert response.approved_appendix.run_summary_ids
    assert response.approved_appendix.audit_log_ids
    assert any(
        "does not imply automatic downstream promotion" in note
        for note in response.approved_appendix.notes
    )

    assert response.linked_run_summary_ids
    assert response.linked_review_decision_ids
    assert response.linked_audit_log_ids
    assert any("explicit approval-only appendix" in note for note in response.notes)

    assert any((response.base_root / "reporting" / "risk_summaries").glob("*.json"))
    assert any((response.base_root / "reporting" / "proposal_scorecards").glob("*.json"))
    assert any((response.base_root / "portfolio" / "paper_position_states").glob("*.json"))
    assert any((response.base_root / "portfolio" / "position_lifecycle_events").glob("*.json"))
    assert any((response.base_root / "portfolio" / "trade_outcomes").glob("*.json"))
    assert any((response.base_root / "portfolio" / "daily_paper_summaries").glob("*.json"))


def test_final_30_day_proof_cli_smoke(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "--fixtures-root",
            str(DEFAULT_FIXTURES_ROOT),
            "--price-fixture-path",
            str(DEFAULT_PRICE_FIXTURE_PATH),
            "--base-root",
            str(tmp_path / "cli_proof"),
            "--requested-by",
            "cli_smoke_test",
            "--frozen-time",
            "2026-04-01T12:00:00Z",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "proof_run_id=" in captured.out
    assert "manifest_path=" in captured.out
    manifest_line = next(
        line for line in captured.out.splitlines() if line.startswith("manifest_path=")
    )
    manifest_path = Path(manifest_line.split("=", 1)[1].strip())
    assert manifest_path.exists()
