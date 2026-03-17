from __future__ import annotations

from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import build_provenance
from libraries.schemas import (
    ArtifactStorageLocation,
    PaperTrade,
    PortfolioConstraint,
    PortfolioProposal,
    PositionIdea,
    ReviewDecision,
    ReviewOutcome,
    RiskCheck,
    StrictModel,
)
from libraries.time import Clock, SystemClock
from libraries.utils import (
    apply_review_decision_to_portfolio_proposal,
    apply_review_decision_to_position_idea,
    make_prefixed_id,
)
from services.paper_execution import PaperExecutionService, PaperTradeProposalRequest
from services.portfolio import (
    PortfolioConstructionService,
    RunPortfolioWorkflowRequest,
    RunPortfolioWorkflowResponse,
)
from services.portfolio.storage import LocalPortfolioArtifactStore


class PortfolioReviewPipelineResponse(StrictModel):
    """End-to-end result of the Day 7 portfolio review pipeline."""

    portfolio_workflow: RunPortfolioWorkflowResponse = Field(
        description="Portfolio proposal workflow output."
    )
    final_position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Final position ideas after any optional review transition.",
    )
    final_portfolio_proposal: PortfolioProposal = Field(
        description="Final portfolio proposal after risk checks and any optional review transition."
    )
    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Risk checks attached to the final proposal.",
    )
    review_decision: ReviewDecision | None = Field(
        default=None,
        description="Optional portfolio-level review decision applied in the pipeline.",
    )
    paper_trades: list[PaperTrade] = Field(
        default_factory=list,
        description="Paper-trade candidates created from the final proposal.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the pipeline.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Pipeline notes describing review state and trade gating.",
    )


def run_portfolio_review_pipeline(
    *,
    signal_root: Path | None = None,
    research_root: Path | None = None,
    ingestion_root: Path | None = None,
    backtesting_root: Path | None = None,
    output_root: Path | None = None,
    company_id: str | None = None,
    constraints: list[PortfolioConstraint] | None = None,
    proposal_review_outcome: ReviewOutcome | None = None,
    reviewer_id: str | None = None,
    review_notes: list[str] | None = None,
    assumed_reference_prices: dict[str, float] | None = None,
    requested_by: str = "pipeline_portfolio_review",
    clock: Clock | None = None,
) -> PortfolioReviewPipelineResponse:
    """Run the deterministic Day 7 portfolio proposal and paper-trade review pipeline."""

    if proposal_review_outcome is not None and reviewer_id is None:
        raise ValueError("reviewer_id is required when proposal_review_outcome is supplied.")

    settings = get_settings()
    resolved_artifact_root = settings.resolved_artifact_root
    resolved_signal_root = signal_root or (resolved_artifact_root / "signal_generation")
    resolved_research_root = research_root or (resolved_artifact_root / "research")
    resolved_ingestion_root = ingestion_root or (resolved_artifact_root / "ingestion")
    resolved_backtesting_root = backtesting_root or (resolved_artifact_root / "backtesting")
    resolved_output_root = output_root or (resolved_artifact_root / "portfolio")
    resolved_clock = clock or SystemClock()
    resolved_review_notes = review_notes or []
    resolved_assumed_prices = assumed_reference_prices or {}

    portfolio_service = PortfolioConstructionService(clock=resolved_clock)
    workflow_response = portfolio_service.run_portfolio_workflow(
        RunPortfolioWorkflowRequest(
            signal_root=resolved_signal_root,
            research_root=resolved_research_root,
            ingestion_root=resolved_ingestion_root,
            backtesting_root=resolved_backtesting_root,
            output_root=resolved_output_root,
            company_id=company_id,
            constraints=constraints or [],
            requested_by=requested_by,
        )
    )
    store = LocalPortfolioArtifactStore(root=resolved_output_root, clock=resolved_clock)
    storage_locations = list(workflow_response.storage_locations)
    notes = list(workflow_response.notes)
    final_position_ideas = list(workflow_response.position_ideas)
    final_portfolio_proposal = workflow_response.portfolio_proposal

    review_decision = None
    if proposal_review_outcome is not None:
        if (
            proposal_review_outcome is ReviewOutcome.APPROVE
            and workflow_response.portfolio_proposal.blocking_issues
        ):
            raise ValueError("Blocking portfolio proposals cannot be approved.")
        review_decision = ReviewDecision(
            review_decision_id=make_prefixed_id("review"),
            target_type="portfolio_proposal",
            target_id=workflow_response.portfolio_proposal.portfolio_proposal_id,
            reviewer_id=reviewer_id or "missing_reviewer",
            outcome=proposal_review_outcome,
            decided_at=resolved_clock.now(),
            rationale=(
                resolved_review_notes[0]
                if resolved_review_notes
                else f"Portfolio review outcome recorded as `{proposal_review_outcome.value}`."
            ),
            blocking_issues=(
                []
                if proposal_review_outcome is ReviewOutcome.APPROVE
                else workflow_response.portfolio_proposal.blocking_issues
            ),
            conditions=[],
            review_notes=resolved_review_notes,
            provenance=build_provenance(
                clock=resolved_clock,
                transformation_name="day7_portfolio_review_decision",
                source_reference_ids=workflow_response.portfolio_proposal.provenance.source_reference_ids,
                upstream_artifact_ids=[
                    workflow_response.portfolio_proposal.portfolio_proposal_id,
                    *[idea.position_idea_id for idea in workflow_response.position_ideas],
                ],
                notes=[f"outcome={proposal_review_outcome.value}"],
            ),
            created_at=resolved_clock.now(),
            updated_at=resolved_clock.now(),
        )
        storage_locations.append(
            store.persist_model(
                artifact_id=review_decision.review_decision_id,
                category="review_decisions",
                model=review_decision,
                source_reference_ids=review_decision.provenance.source_reference_ids,
            )
        )
        final_position_ideas = [
            apply_review_decision_to_position_idea(
                position_idea=position_idea,
                review_decision=review_decision,
            )
            for position_idea in workflow_response.position_ideas
        ]
        final_portfolio_proposal = apply_review_decision_to_portfolio_proposal(
            portfolio_proposal=workflow_response.portfolio_proposal.model_copy(
                update={
                    "position_ideas": final_position_ideas,
                }
            ),
            review_decision=review_decision,
        )
        for position_idea in final_position_ideas:
            storage_locations.append(
                store.persist_model(
                    artifact_id=position_idea.position_idea_id,
                    category="position_ideas",
                    model=position_idea,
                    source_reference_ids=position_idea.provenance.source_reference_ids,
                )
            )
        storage_locations.append(
            store.persist_model(
                artifact_id=final_portfolio_proposal.portfolio_proposal_id,
                category="portfolio_proposals",
                model=final_portfolio_proposal,
                source_reference_ids=final_portfolio_proposal.provenance.source_reference_ids,
            )
        )
        notes.append(f"proposal_review_outcome={proposal_review_outcome.value}")

    paper_execution_service = PaperExecutionService(clock=resolved_clock)
    paper_trade_response = paper_execution_service.propose_trades(
        PaperTradeProposalRequest(
            portfolio_proposal=final_portfolio_proposal,
            assumed_reference_prices=resolved_assumed_prices,
            requested_by=requested_by,
        )
    )
    notes.extend(paper_trade_response.notes)
    for paper_trade in paper_trade_response.proposed_trades:
        storage_locations.append(
            store.persist_model(
                artifact_id=paper_trade.paper_trade_id,
                category="paper_trades",
                model=paper_trade,
                source_reference_ids=paper_trade.provenance.source_reference_ids,
            )
        )

    return PortfolioReviewPipelineResponse(
        portfolio_workflow=workflow_response,
        final_position_ideas=final_position_ideas,
        final_portfolio_proposal=final_portfolio_proposal,
        risk_checks=final_portfolio_proposal.risk_checks,
        review_decision=review_decision,
        paper_trades=paper_trade_response.proposed_trades,
        storage_locations=storage_locations,
        notes=notes,
    )
