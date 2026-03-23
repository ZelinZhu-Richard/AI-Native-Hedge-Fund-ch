from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import ReviewTargetType, WorkflowStatus
from libraries.time import FrozenClock
from pipelines.daily_operations import run_daily_workflow

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
FIXED_NOW = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)


def test_daily_workflow_runs_local_stack_and_stops_at_review_gate(tmp_path: Path) -> None:
    artifact_root = tmp_path / "daily_run"

    response = run_daily_workflow(
        artifact_root=artifact_root,
        fixtures_root=FIXTURE_ROOT,
        as_of_time=FIXED_NOW,
        requested_by="integration_test",
        clock=FrozenClock(FIXED_NOW),
    )

    assert response.workflow_execution.status is WorkflowStatus.ATTENTION_REQUIRED
    assert response.fixture_refresh_and_normalization
    assert response.evidence_extraction
    assert response.research_workflow is not None
    assert response.feature_signal_pipeline is not None
    assert response.portfolio_workflow is not None
    assert response.review_queue_sync is not None
    assert response.paper_trade_candidate_generation is not None
    assert response.operations_health_checks is not None
    assert response.recent_run_summaries is not None
    assert response.risk_summary is not None
    assert response.proposal_scorecard is not None
    assert response.daily_system_report is not None
    assert response.paper_trade_candidate_generation.proposed_trades == []
    assert response.paper_trade_candidate_generation.validation_gate is not None
    assert response.workflow_execution.linked_run_summary_ids
    assert response.portfolio_workflow is not None
    assert response.portfolio_workflow.portfolio_proposal.proposal_scorecard_id == (
        response.proposal_scorecard.proposal_scorecard_id
    )
    assert response.daily_system_report.proposal_scorecard_ids == [
        response.proposal_scorecard.proposal_scorecard_id
    ]

    queue_target_types = {item.target_type for item in response.review_queue_sync.queue_items}
    assert {
        ReviewTargetType.RESEARCH_BRIEF,
        ReviewTargetType.SIGNAL,
        ReviewTargetType.PORTFOLIO_PROPOSAL,
    }.issubset(queue_target_types)

    categories = {
        "workflow_definitions",
        "scheduled_run_configs",
        "workflow_executions",
        "run_steps",
        "runbook_entries",
    }
    for category in categories:
        assert any((artifact_root / "orchestration" / category).glob("*.json"))

    paper_trade_step = next(
        step for step in response.run_steps if step.step_name == "paper_trade_candidate_generation"
    )
    assert paper_trade_step.status is WorkflowStatus.ATTENTION_REQUIRED
    assert paper_trade_step.manual_intervention_requirement is not None
    assert paper_trade_step.manual_intervention_requirement.gate_reason.startswith(
        "Review-bound stop:"
    )
    assert response.paper_trade_candidate_generation.validation_gate.validation_gate_id in (
        paper_trade_step.produced_artifact_ids
    )
    assert response.paper_trade_candidate_generation.validation_gate.validation_gate_id in (
        response.workflow_execution.produced_artifact_ids
    )
    assert "paper_trade_stop_kind=review_bound" in response.paper_trade_candidate_generation.notes
    assert any("paper_trade_stop_kind=review_bound" == note for note in paper_trade_step.notes)
    assert any("review-bound approval gate" in note for note in paper_trade_step.notes)
    assert any(step.child_run_summary_ids for step in response.run_steps)
    assert any((artifact_root / "reporting" / "risk_summaries").glob("*.json"))
    assert any((artifact_root / "reporting" / "proposal_scorecards").glob("*.json"))
    assert any((artifact_root / "reporting" / "review_queue_summaries").glob("*.json"))
    assert any((artifact_root / "reporting" / "daily_system_reports").glob("*.json"))

    assert any(
        location.uri.startswith("file://") for location in response.storage_locations
    )
