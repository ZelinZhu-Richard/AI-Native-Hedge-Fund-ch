from __future__ import annotations

from fastapi import APIRouter

from apps.api.builders import build_response_envelope
from apps.api.contracts import PaperTradeListPayload, PortfolioProposalListPayload
from apps.api.state import api_clock, artifact_root, load_persisted_models
from libraries.schemas import APIResponseEnvelope, PaperTrade, PortfolioProposal

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio/proposals", response_model=APIResponseEnvelope[PortfolioProposalListPayload])
@router.get(
    "/portfolio-proposals",
    response_model=APIResponseEnvelope[PortfolioProposalListPayload],
    include_in_schema=False,
)
def list_portfolio_proposals() -> APIResponseEnvelope[PortfolioProposalListPayload]:
    """Return persisted portfolio proposals when they exist."""

    items = load_persisted_models(
        artifact_root() / "portfolio" / "portfolio_proposals",
        PortfolioProposal,
    )
    return build_response_envelope(
        data=PortfolioProposalListPayload(items=items, total=len(items)),
        generated_at=api_clock.now(),
    )


@router.get("/portfolio/paper-trades", response_model=APIResponseEnvelope[PaperTradeListPayload])
@router.get(
    "/paper-trades/proposals",
    response_model=APIResponseEnvelope[PaperTradeListPayload],
    include_in_schema=False,
)
def list_paper_trade_proposals() -> APIResponseEnvelope[PaperTradeListPayload]:
    """Return persisted paper-trade proposals when they exist."""

    items = load_persisted_models(
        artifact_root() / "portfolio" / "paper_trades",
        PaperTrade,
    )
    return build_response_envelope(
        data=PaperTradeListPayload(items=items, total=len(items)),
        generated_at=api_clock.now(),
    )
