from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.builders import build_response_envelope
from apps.api.state import api_clock, artifact_root
from libraries.schemas import (
    APIResponseEnvelope,
    DailySystemReport,
    ProposalScorecard,
    ReviewQueueSummary,
)
from services.reporting.loaders import (
    latest_proposal_scorecard,
    load_reporting_workspace,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily-system/latest", response_model=APIResponseEnvelope[DailySystemReport])
def latest_daily_system_report() -> APIResponseEnvelope[DailySystemReport]:
    """Return the latest grounded daily system report when available."""

    workspace = load_reporting_workspace(artifact_root() / "reporting")
    if not workspace.daily_system_reports:
        raise HTTPException(status_code=404, detail="No daily system report is available.")
    report = workspace.daily_system_reports[0]
    return build_response_envelope(data=report, generated_at=api_clock.now())


@router.get(
    "/proposals/{portfolio_proposal_id}/scorecard",
    response_model=APIResponseEnvelope[ProposalScorecard],
)
def proposal_scorecard(
    portfolio_proposal_id: str,
) -> APIResponseEnvelope[ProposalScorecard]:
    """Return the latest grounded proposal scorecard for one proposal when available."""

    workspace = load_reporting_workspace(artifact_root() / "reporting")
    scorecard = latest_proposal_scorecard(workspace, portfolio_proposal_id)
    if scorecard is None:
        raise HTTPException(
            status_code=404,
            detail=f"No proposal scorecard exists for `{portfolio_proposal_id}`.",
        )
    return build_response_envelope(data=scorecard, generated_at=api_clock.now())


@router.get("/review-queue/latest", response_model=APIResponseEnvelope[ReviewQueueSummary])
def latest_review_queue_summary() -> APIResponseEnvelope[ReviewQueueSummary]:
    """Return the latest grounded review-queue summary when available."""

    workspace = load_reporting_workspace(artifact_root() / "reporting")
    if not workspace.review_queue_summaries:
        raise HTTPException(status_code=404, detail="No review-queue summary is available.")
    report = workspace.review_queue_summaries[0]
    return build_response_envelope(data=report, generated_at=api_clock.now())
