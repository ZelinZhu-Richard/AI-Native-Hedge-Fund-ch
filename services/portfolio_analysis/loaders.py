from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.core import load_local_models
from libraries.schemas import (
    Company,
    ConstraintResult,
    ConstraintSet,
    ConstructionDecision,
    PortfolioProposal,
    PortfolioSelectionSummary,
    PositionSizingRationale,
    Signal,
    StrictModel,
)
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
    constraint_set: ConstraintSet | None = Field(
        default=None,
        description="Applied portfolio-construction constraint set when available.",
    )
    constraint_results_by_id: dict[str, ConstraintResult] = Field(
        default_factory=dict,
        description="Constraint results keyed by identifier when construction artifacts exist.",
    )
    position_sizing_rationales_by_id: dict[str, PositionSizingRationale] = Field(
        default_factory=dict,
        description="Position-sizing rationales keyed by identifier when available.",
    )
    construction_decisions_by_id: dict[str, ConstructionDecision] = Field(
        default_factory=dict,
        description="Construction decisions keyed by identifier when available.",
    )
    portfolio_selection_summary: PortfolioSelectionSummary | None = Field(
        default=None,
        description="Portfolio-construction summary when available.",
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
    constraint_sets = _load_models(portfolio_root / "constraint_sets", ConstraintSet)
    constraint_results = _load_models(portfolio_root / "constraint_results", ConstraintResult)
    position_sizing_rationales = _load_models(
        portfolio_root / "position_sizing_rationales", PositionSizingRationale
    )
    construction_decisions = _load_models(
        portfolio_root / "construction_decisions", ConstructionDecision
    )
    portfolio_selection_summary = None
    if portfolio_proposal.portfolio_selection_summary_id is not None:
        summary_path = (
            portfolio_root
            / "portfolio_selection_summaries"
            / f"{portfolio_proposal.portfolio_selection_summary_id}.json"
        )
        if summary_path.exists():
            portfolio_selection_summary = PortfolioSelectionSummary.model_validate_json(
                summary_path.read_text(encoding="utf-8")
            )
    constraint_set = (
        next(
            (
                constraint_set
                for constraint_set in constraint_sets
                if portfolio_selection_summary is not None
                and constraint_set.constraint_set_id == portfolio_selection_summary.constraint_set_id
            ),
            None,
        )
        if portfolio_selection_summary is not None
        else None
    )
    return LoadedPortfolioAnalysisInputs(
        portfolio_proposal=portfolio_proposal,
        signals_by_id=signals_by_id,
        companies_by_id=companies_by_id,
        constraint_set=constraint_set,
        constraint_results_by_id={
            result.constraint_result_id: result
            for result in constraint_results
            if constraint_set is not None and result.constraint_set_id == constraint_set.constraint_set_id
        },
        position_sizing_rationales_by_id={
            rationale.position_sizing_rationale_id: rationale
            for rationale in position_sizing_rationales
        },
        construction_decisions_by_id={
            decision.construction_decision_id: decision
            for decision in construction_decisions
            if portfolio_selection_summary is not None
            and decision.portfolio_selection_summary_id
            == portfolio_selection_summary.portfolio_selection_summary_id
        },
        portfolio_selection_summary=portfolio_selection_summary,
    )


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from one category directory."""

    return load_local_models(directory, model_cls)
