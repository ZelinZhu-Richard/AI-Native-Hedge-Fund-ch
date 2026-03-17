from __future__ import annotations

from libraries.schemas.base import (
    PaperTradeStatus,
    PortfolioProposalStatus,
    PositionIdeaStatus,
    ReviewOutcome,
)
from libraries.schemas.portfolio import PaperTrade, PortfolioProposal, PositionIdea, ReviewDecision


def position_idea_status_from_review_outcome(outcome: ReviewOutcome) -> PositionIdeaStatus:
    """Map a review outcome onto the position-idea lifecycle."""

    return {
        ReviewOutcome.APPROVE: PositionIdeaStatus.APPROVED_FOR_PORTFOLIO,
        ReviewOutcome.NEEDS_REVISION: PositionIdeaStatus.DRAFT,
        ReviewOutcome.REJECT: PositionIdeaStatus.REJECTED,
        ReviewOutcome.ESCALATE: PositionIdeaStatus.PENDING_REVIEW,
    }[outcome]


def portfolio_proposal_status_from_review_outcome(
    outcome: ReviewOutcome,
) -> PortfolioProposalStatus:
    """Map a review outcome onto the portfolio-proposal lifecycle."""

    return {
        ReviewOutcome.APPROVE: PortfolioProposalStatus.APPROVED,
        ReviewOutcome.NEEDS_REVISION: PortfolioProposalStatus.DRAFT,
        ReviewOutcome.REJECT: PortfolioProposalStatus.REJECTED,
        ReviewOutcome.ESCALATE: PortfolioProposalStatus.PENDING_REVIEW,
    }[outcome]


def paper_trade_status_from_review_outcome(outcome: ReviewOutcome) -> PaperTradeStatus:
    """Map a review outcome onto the paper-trade lifecycle."""

    return {
        ReviewOutcome.APPROVE: PaperTradeStatus.APPROVED,
        ReviewOutcome.NEEDS_REVISION: PaperTradeStatus.PROPOSED,
        ReviewOutcome.REJECT: PaperTradeStatus.REJECTED,
        ReviewOutcome.ESCALATE: PaperTradeStatus.PROPOSED,
    }[outcome]


def apply_review_decision_to_position_idea(
    *,
    position_idea: PositionIdea,
    review_decision: ReviewDecision,
) -> PositionIdea:
    """Apply one review decision to a position idea."""

    return position_idea.model_copy(
        update={
            "status": position_idea_status_from_review_outcome(review_decision.outcome),
            "review_decision_ids": [
                *position_idea.review_decision_ids,
                review_decision.review_decision_id,
            ],
            "updated_at": review_decision.decided_at,
        }
    )


def apply_review_decision_to_portfolio_proposal(
    *,
    portfolio_proposal: PortfolioProposal,
    review_decision: ReviewDecision,
) -> PortfolioProposal:
    """Apply one review decision to a portfolio proposal."""

    blocking_issues = (
        portfolio_proposal.blocking_issues
        if review_decision.outcome is ReviewOutcome.APPROVE
        else sorted(
            {
                *portfolio_proposal.blocking_issues,
                *review_decision.blocking_issues,
            }
        )
    )
    return portfolio_proposal.model_copy(
        update={
            "status": portfolio_proposal_status_from_review_outcome(review_decision.outcome),
            "review_decision_ids": [
                *portfolio_proposal.review_decision_ids,
                review_decision.review_decision_id,
            ],
            "blocking_issues": blocking_issues,
            "updated_at": review_decision.decided_at,
        }
    )


def apply_review_decision_to_paper_trade(
    *,
    paper_trade: PaperTrade,
    review_decision: ReviewDecision,
) -> PaperTrade:
    """Apply one review decision to a paper trade candidate."""

    approved = review_decision.outcome is ReviewOutcome.APPROVE
    return paper_trade.model_copy(
        update={
            "status": paper_trade_status_from_review_outcome(review_decision.outcome),
            "approved_at": review_decision.decided_at if approved else paper_trade.approved_at,
            "approved_by": review_decision.reviewer_id if approved else paper_trade.approved_by,
            "review_decision_ids": [
                *paper_trade.review_decision_ids,
                review_decision.review_decision_id,
            ],
            "updated_at": review_decision.decided_at,
        }
    )
