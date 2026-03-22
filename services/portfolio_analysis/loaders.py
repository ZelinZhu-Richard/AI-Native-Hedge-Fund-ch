from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.schemas import Company, PortfolioProposal, Signal, StrictModel
from libraries.schemas.base import TimestampedModel

T = TypeVar("T", bound=TimestampedModel)


class LoadedPortfolioAnalysisInputs(StrictModel):
    """Typed bundle of persisted artifacts used for portfolio analysis."""

    portfolio_proposal: PortfolioProposal = Field(description="Portfolio proposal under analysis.")
    signals_by_id: dict[str, Signal] = Field(
        default_factory=dict,
        description="Signals keyed by ID for the proposal slice.",
    )
    companies_by_id: dict[str, Company] = Field(
        default_factory=dict,
        description="Resolved company metadata keyed by company ID when available.",
    )


def load_portfolio_analysis_inputs(
    *,
    portfolio_root: Path,
    signal_root: Path,
    ingestion_root: Path | None,
    portfolio_proposal_id: str,
) -> LoadedPortfolioAnalysisInputs:
    """Load persisted proposal, signal, and company artifacts for analysis."""

    proposal_path = portfolio_root / "portfolio_proposals" / f"{portfolio_proposal_id}.json"
    if not proposal_path.exists():
        raise ValueError(f"Portfolio proposal `{portfolio_proposal_id}` was not found.")
    portfolio_proposal = PortfolioProposal.model_validate_json(
        proposal_path.read_text(encoding="utf-8")
    )
    signal_ids = {idea.signal_id for idea in portfolio_proposal.position_ideas if idea.signal_id}
    signals_by_id = {
        signal.signal_id: signal
        for signal in _load_models(signal_root / "signals", Signal)
        if signal.signal_id in signal_ids
    }
    companies_by_id: dict[str, Company] = {}
    if ingestion_root is not None:
        companies_by_id = {
            company.company_id: company
            for company in _load_models(ingestion_root / "normalized" / "companies", Company)
        }
    return LoadedPortfolioAnalysisInputs(
        portfolio_proposal=portfolio_proposal,
        signals_by_id=signals_by_id,
        companies_by_id=companies_by_id,
    )


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from one category directory."""

    if not directory.exists():
        return []
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
