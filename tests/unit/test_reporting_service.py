from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    ActionRecommendationSummary,
    AlertRecord,
    AlertState,
    EscalationStatus,
    HealthCheckStatus,
    ReviewFollowup,
    ReviewFollowupStatus,
    ReviewOutcome,
    ReviewQueueItem,
    ReviewQueueStatus,
    ReviewTargetType,
    RunSummary,
    ServiceStatus,
    Severity,
    WorkflowStatus,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.time import FrozenClock
from services.reporting import (
    GenerateDailySystemReportRequest,
    GenerateReviewQueueSummaryRequest,
    ReportingService,
)

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_review_queue_summary_counts_attention_and_grounding(tmp_path: Path) -> None:
    service = ReportingService(clock=FrozenClock(FIXED_NOW))
    response = service.generate_review_queue_summary(
        GenerateReviewQueueSummaryRequest(
            queue_items=[
                _queue_item(
                    review_queue_item_id="rqitem_research",
                    target_type=ReviewTargetType.RESEARCH_BRIEF,
                    queue_status=ReviewQueueStatus.PENDING_REVIEW,
                    escalation_status=EscalationStatus.NONE,
                    assigned=False,
                ),
                _queue_item(
                    review_queue_item_id="rqitem_signal",
                    target_type=ReviewTargetType.SIGNAL,
                    queue_status=ReviewQueueStatus.ESCALATED,
                    escalation_status=EscalationStatus.ESCALATED,
                    assigned=True,
                ),
            ],
            requested_by="unit_test",
        ),
        output_root=tmp_path / "reporting",
    )

    summary = response.review_queue_summary
    assert summary.counts_by_target_type["research_brief"] == 1
    assert summary.counts_by_target_type["signal"] == 1
    assert summary.escalated_item_ids == ["rqitem_signal"]
    assert summary.unassigned_item_ids == ["rqitem_research"]
    assert set(summary.attention_required_item_ids) == {
        "rqitem_research",
        "rqitem_signal",
    }
    assert response.reporting_context.source_artifact_ids == [
        "rqitem_research",
        "rqitem_signal",
    ]
    assert (tmp_path / "reporting" / "review_queue_summaries").exists()


def test_daily_system_report_preserves_missing_inputs_and_open_followups(
    tmp_path: Path,
) -> None:
    service = ReportingService(clock=FrozenClock(FIXED_NOW))
    queue_summary = service.generate_review_queue_summary(
        GenerateReviewQueueSummaryRequest(
            queue_items=[
                _queue_item(
                    review_queue_item_id="rqitem_proposal",
                    target_type=ReviewTargetType.PORTFOLIO_PROPOSAL,
                    queue_status=ReviewQueueStatus.PENDING_REVIEW,
                    escalation_status=EscalationStatus.NONE,
                    assigned=False,
                )
            ],
            requested_by="unit_test",
        ),
        output_root=tmp_path / "reporting",
    ).review_queue_summary
    response = service.generate_daily_system_report(
        GenerateDailySystemReportRequest(
            report_date=date(2026, 3, 22),
            run_summaries=[
                RunSummary(
                    run_summary_id="runsum_test",
                    workflow_name="portfolio_review_pipeline",
                    workflow_run_id="run_test",
                    service_name="portfolio",
                    status=WorkflowStatus.ATTENTION_REQUIRED,
                    requested_by="unit_test",
                    started_at=FIXED_NOW,
                    completed_at=FIXED_NOW,
                    produced_artifact_ids=["proposal_test"],
                    produced_artifact_counts={"portfolio_proposals": 1},
                    storage_locations=[],
                    pipeline_event_ids=[],
                    alert_record_ids=[],
                    failure_messages=["risk_check_failed"],
                    attention_reasons=["proposal_not_approved_for_paper_trade"],
                    notes=[],
                    provenance=_provenance(),
                    created_at=FIXED_NOW,
                    updated_at=FIXED_NOW,
                )
            ],
            alert_records=[
                AlertRecord(
                    alert_record_id="alert_test",
                    alert_condition_id="alert_condition_test",
                    service_name="portfolio",
                    workflow_name="portfolio_review_pipeline",
                    workflow_run_id="run_test",
                    severity=Severity.HIGH,
                    state=AlertState.OPEN,
                    triggered_at=FIXED_NOW,
                    message="Portfolio review needs operator attention.",
                    related_artifact_ids=["proposal_test"],
                    provenance=_provenance(),
                    created_at=FIXED_NOW,
                    updated_at=FIXED_NOW,
                )
            ],
            service_statuses=[
                ServiceStatus(
                    service_name="portfolio",
                    capability_description="Portfolio proposal construction and review.",
                    status=HealthCheckStatus.WARN,
                    last_checked_at=FIXED_NOW,
                    recent_run_summary_ids=["runsum_test"],
                    open_alert_count=1,
                    notes=["Attention required."],
                )
            ],
            review_queue_summary=queue_summary,
            daily_paper_summaries=[],
            review_followups=[
                ReviewFollowup(
                    review_followup_id="followup_test",
                    paper_trade_id="trade_test",
                    paper_position_state_id="ppos_test",
                    trade_outcome_id=None,
                    status=ReviewFollowupStatus.OPEN,
                    instruction="Add reference price coverage before daily summary review.",
                    owner_id="ops_1",
                    related_artifact_ids=["trade_test"],
                    summary="Paper trade is missing mark coverage.",
                    provenance=_provenance(),
                    created_at=FIXED_NOW,
                    updated_at=FIXED_NOW,
                )
            ],
            proposal_scorecards=[],
            experiment_scorecards=[],
            requested_by="unit_test",
        ),
        output_root=tmp_path / "reporting",
    )

    report = response.daily_system_report
    assert "daily_paper_summary_missing" in report.missing_information
    assert "proposal_scorecards_missing" in report.missing_information
    assert "experiment_scorecards_missing" in report.missing_information
    assert "Portfolio review needs operator attention." in report.notable_failures
    assert "Paper trade is missing mark coverage." in report.attention_reasons
    assert response.reporting_context.warning_artifact_ids
    assert (tmp_path / "reporting" / "daily_system_reports").exists()


def _queue_item(
    *,
    review_queue_item_id: str,
    target_type: ReviewTargetType,
    queue_status: ReviewQueueStatus,
    escalation_status: EscalationStatus,
    assigned: bool,
) -> ReviewQueueItem:
    return ReviewQueueItem(
        review_queue_item_id=review_queue_item_id,
        target_type=target_type,
        target_id=f"{target_type.value}_test",
        queue_status=queue_status,
        current_target_status="pending_review",
        title=f"{target_type.value} review",
        summary="Pending review.",
        submitted_at=FIXED_NOW,
        escalation_status=escalation_status,
        action_recommendation=ActionRecommendationSummary(
            recommended_outcome=ReviewOutcome.NEEDS_REVISION,
            summary="Review before downstream use.",
            blocking_reasons=[] if assigned else ["missing_assignment"],
            warnings=["operator_attention_required"],
            follow_up_actions=["Assign reviewer."],
        ),
        review_note_ids=[],
        review_decision_ids=[],
        review_assignment_id="assign_test" if assigned else None,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
