from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TypeVar

from libraries.core import load_local_models
from libraries.schemas import (
    AssumptionMismatch,
    AvailabilityMismatch,
    BacktestRun,
    CostModel,
    ExecutionTimingRule,
    FillAssumption,
    PaperTrade,
    PortfolioProposal,
    RealismWarning,
    ReconciliationReport,
    ReviewDecision,
    ReviewTargetType,
    Signal,
    StrategyToPaperMapping,
)
from libraries.schemas.base import TimestampedModel

TModel = TypeVar("TModel", bound=TimestampedModel)


def load_backtest_runs(
    *,
    backtesting_root: Path,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
) -> list[BacktestRun]:
    """Load persisted backtest runs with optional company and time filtering."""

    runs = _apply_created_at_cutoff(
        load_local_models(backtesting_root / "runs", BacktestRun),
        as_of_time=as_of_time,
    )
    if company_id is None:
        return runs
    return [run for run in runs if run.company_id == company_id]


def load_portfolio_proposals(
    *,
    portfolio_root: Path,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
) -> list[PortfolioProposal]:
    """Load persisted portfolio proposals with optional derived company filtering."""

    proposals = _apply_created_at_cutoff(
        load_local_models(portfolio_root / "portfolio_proposals", PortfolioProposal),
        as_of_time=as_of_time,
    )
    if company_id is None:
        return proposals
    return [proposal for proposal in proposals if proposal_company_id(proposal) == company_id]


def load_paper_trades(
    *,
    portfolio_root: Path,
    proposal_id: str | None = None,
    as_of_time: datetime | None = None,
) -> list[PaperTrade]:
    """Load persisted paper trades with optional proposal linkage filtering."""

    trades = _apply_created_at_cutoff(
        load_local_models(portfolio_root / "paper_trades", PaperTrade),
        as_of_time=as_of_time,
    )
    if proposal_id is None:
        return trades
    return [trade for trade in trades if trade.portfolio_proposal_id == proposal_id]


def load_execution_timing_rules(root: Path) -> list[ExecutionTimingRule]:
    """Load persisted execution-timing rules."""

    return load_local_models(root / "execution_timing_rules", ExecutionTimingRule)


def load_fill_assumptions(root: Path) -> list[FillAssumption]:
    """Load persisted fill assumptions."""

    return load_local_models(root / "fill_assumptions", FillAssumption)


def load_cost_models(root: Path) -> list[CostModel]:
    """Load persisted cost models."""

    return load_local_models(root / "cost_models", CostModel)


def load_strategy_to_paper_mappings(root: Path) -> list[StrategyToPaperMapping]:
    """Load persisted strategy-to-paper mappings."""

    return load_local_models(root / "strategy_to_paper_mappings", StrategyToPaperMapping)


def load_reconciliation_reports(root: Path) -> list[ReconciliationReport]:
    """Load persisted reconciliation reports."""

    return load_local_models(root / "reconciliation_reports", ReconciliationReport)


def load_assumption_mismatches(root: Path) -> list[AssumptionMismatch]:
    """Load persisted assumption mismatches."""

    return load_local_models(root / "assumption_mismatches", AssumptionMismatch)


def load_availability_mismatches(root: Path) -> list[AvailabilityMismatch]:
    """Load persisted availability mismatches."""

    return load_local_models(root / "availability_mismatches", AvailabilityMismatch)


def load_realism_warnings(root: Path) -> list[RealismWarning]:
    """Load persisted realism warnings."""

    return load_local_models(root / "realism_warnings", RealismWarning)


def load_signals(signal_root: Path) -> list[Signal]:
    """Load persisted research signals."""

    return load_local_models(signal_root / "signals", Signal)


def load_review_decisions(*, review_root: Path, portfolio_root: Path) -> list[ReviewDecision]:
    """Load review decisions from the review root and legacy portfolio location."""

    primary = {
        decision.review_decision_id: decision
        for decision in load_local_models(review_root / "review_decisions", ReviewDecision)
    }
    for decision in load_local_models(portfolio_root / "review_decisions", ReviewDecision):
        primary.setdefault(decision.review_decision_id, decision)
    return list(primary.values())


def latest_portfolio_proposal_review_decision_time(
    *,
    review_root: Path,
    portfolio_root: Path,
    proposal_id: str,
) -> datetime | None:
    """Return the latest explicit review-decision time for one portfolio proposal when available."""

    matching = [
        decision
        for decision in load_review_decisions(review_root=review_root, portfolio_root=portfolio_root)
        if decision.target_type is ReviewTargetType.PORTFOLIO_PROPOSAL
        and decision.target_id == proposal_id
    ]
    if not matching:
        return None
    return max(decision.decided_at for decision in matching)


def proposal_company_id(proposal: PortfolioProposal) -> str | None:
    """Resolve one proposal-scoped company identifier from position ideas when possible."""

    company_ids = {idea.company_id for idea in proposal.position_ideas}
    if len(company_ids) != 1:
        return None
    return next(iter(company_ids))


def _apply_created_at_cutoff(
    artifacts: list[TModel],
    *,
    as_of_time: datetime | None,
) -> list[TModel]:
    """Apply an optional creation-time cutoff to persisted artifacts."""

    if as_of_time is None:
        return artifacts
    return [artifact for artifact in artifacts if artifact.created_at <= as_of_time]
