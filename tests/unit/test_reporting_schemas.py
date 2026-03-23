from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    DailySystemReport,
    ExperimentScorecard,
    HealthCheckStatus,
    PortfolioExposureSummary,
    PortfolioProposal,
    ProposalScorecard,
    ReportingAudience,
    ReportingContext,
    ResearchSummary,
    ReviewContext,
    ScorecardMeasure,
    SystemCapabilitySummary,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_scorecard_measure_requires_explicit_basis_and_linked_artifacts() -> None:
    with pytest.raises(ValidationError):
        ScorecardMeasure(
            measure_name="evaluation_coverage",
            measure_basis="",
            status=HealthCheckStatus.WARN,
            linked_artifact_ids=[],
            notes=[],
        )


def test_reporting_context_requires_subject_linkage() -> None:
    with pytest.raises(ValidationError):
        ReportingContext(
            audience=ReportingAudience.OPERATOR,
            subject_type="",
            subject_id="daily_report",
            source_artifact_ids=["runsum_test"],
            warning_artifact_ids=[],
            refusal_or_quarantine_artifact_ids=[],
            missing_inputs=[],
            notes=[],
        )


def test_grounded_summary_and_scorecard_schemas_require_source_truth() -> None:
    with pytest.raises(ValidationError):
        ResearchSummary(
            research_summary_id="rsum_test",
            research_brief_id="brief_test",
            company_id="co_test",
            source_artifact_ids=[],
            warning_artifact_ids=[],
            refusal_or_quarantine_artifact_ids=[],
            key_findings=["Finding."],
            uncertainty_notes=["Uncertainty remains visible."],
            missing_information=[],
            summary="",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )

    with pytest.raises(ValidationError):
        ExperimentScorecard(
            experiment_scorecard_id="expsc_test",
            experiment_id="exp_test",
            measures=[],
            warning_artifact_ids=[],
            source_artifact_ids=["exp_test"],
            missing_information=[],
            summary="Missing measures should fail.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )

    with pytest.raises(ValidationError):
        ProposalScorecard(
            proposal_scorecard_id="propsc_test",
            portfolio_proposal_id="proposal_test",
            measures=[],
            blocking_findings=[],
            warnings=[],
            source_artifact_ids=["proposal_test"],
            warning_artifact_ids=[],
            missing_information=[],
            summary="Missing measures should fail.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_daily_report_capability_summary_and_additive_fields_validate() -> None:
    proposal = PortfolioProposal.model_validate(
        {
            "portfolio_proposal_id": "proposal_test",
            "name": "test proposal",
            "status": "pending_review",
            "as_of_time": FIXED_NOW,
            "generated_at": FIXED_NOW,
            "position_ideas": [],
            "constraints": [],
            "risk_checks": [],
            "exposure_summary": PortfolioExposureSummary(
                portfolio_exposure_summary_id="pexp_test",
                gross_exposure_bps=0,
                net_exposure_bps=0,
                long_exposure_bps=0,
                short_exposure_bps=0,
                cash_buffer_bps=10_000,
                position_count=0,
                turnover_bps_assumption=0,
                provenance=_provenance(),
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            ),
            "blocking_issues": [],
            "review_decision_ids": [],
            "proposal_scorecard_id": "propsc_test",
            "review_required": True,
            "summary": "Grounded proposal.",
            "provenance": {"processing_time": FIXED_NOW.isoformat().replace("+00:00", "Z")},
            "created_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
            "updated_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
        }
    )
    review_context = ReviewContext.model_validate(
        {
            "queue_item": {
                "review_queue_item_id": "rqitem_test",
                "target_type": "portfolio_proposal",
                "target_id": "proposal_test",
                "queue_status": "pending_review",
                "current_target_status": "pending_review",
                "title": "Proposal review",
                "summary": "Pending review.",
                "submitted_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
                "escalation_status": "none",
                "action_recommendation": {
                    "recommended_outcome": "needs_revision",
                    "summary": "Needs review.",
                    "blocking_reasons": [],
                    "warnings": [],
                    "follow_up_actions": [],
                },
                "review_note_ids": [],
                "review_decision_ids": [],
                "review_assignment_id": None,
                "provenance": {"processing_time": FIXED_NOW.isoformat().replace("+00:00", "Z")},
                "created_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
                "updated_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
                },
                "portfolio_proposal": proposal.model_dump(mode="json"),
                "proposal_scorecard": {
                    "proposal_scorecard_id": "propsc_test",
                "portfolio_proposal_id": "proposal_test",
                "measures": [
                    {
                        "measure_name": "construction_traceability",
                        "measure_basis": "Construction summary is present.",
                        "status": "pass",
                        "linked_artifact_ids": ["proposal_test"],
                        "notes": [],
                    }
                ],
                "blocking_findings": [],
                "warnings": [],
                "source_artifact_ids": ["proposal_test"],
                "warning_artifact_ids": [],
                "missing_information": [],
                "summary": "Grounded scorecard.",
                "provenance": {"processing_time": FIXED_NOW.isoformat().replace("+00:00", "Z")},
                "created_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
                "updated_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
            },
            "review_notes": [],
            "review_decisions": [],
            "audit_logs": [],
            "related_prior_work": None,
            "action_recommendation": {
                "recommended_outcome": "needs_revision",
                "summary": "Needs review.",
                "blocking_reasons": [],
                "warnings": [],
                "follow_up_actions": [],
            },
        }
    )
    daily_report = DailySystemReport(
        daily_system_report_id="dsrpt_test",
        report_date=date(2026, 3, 22),
        run_summary_ids=["runsum_test"],
        alert_record_ids=["alert_test"],
        service_statuses=[],
        review_queue_summary_id="rqsum_test",
        daily_paper_summary_ids=[],
        open_review_followup_ids=[],
        proposal_scorecard_ids=["propsc_test"],
        experiment_scorecard_ids=[],
        source_artifact_ids=["runsum_test", "alert_test"],
        notable_failures=["ingestion failure"],
        attention_reasons=["queue review required"],
        missing_information=["daily_paper_summary_missing"],
        summary="Grounded daily system report.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    capability_summary = SystemCapabilitySummary(
        system_capability_summary_id="capsum_test",
        capability_name="reporting",
        service_names=["reporting"],
        evidence_artifact_ids=["dsrpt_test"],
        recent_run_summary_ids=["runsum_test"],
        alert_record_ids=["alert_test"],
        current_limitations=["No dashboard UI."],
        maturity_notes=["Deterministic artifact-backed reporting only."],
        source_artifact_ids=["runsum_test", "alert_test"],
        warning_artifact_ids=["alert_test"],
        summary="Reporting capability is grounded but intentionally simple.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert proposal.proposal_scorecard_id == "propsc_test"
    assert review_context.proposal_scorecard is not None
    assert daily_report.proposal_scorecard_ids == ["propsc_test"]
    assert capability_summary.service_names == ["reporting"]


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
