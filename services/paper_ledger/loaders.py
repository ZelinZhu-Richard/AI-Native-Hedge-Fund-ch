from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.core import load_local_models
from libraries.schemas import (
    DailyPaperSummary,
    OutcomeAttribution,
    PaperLedgerEntry,
    PaperPositionState,
    PaperTrade,
    PortfolioProposal,
    PositionIdea,
    PositionLifecycleEvent,
    ReviewDecision,
    ReviewFollowup,
    ReviewNote,
    ReviewTargetType,
    Signal,
    StrictModel,
    TradeOutcome,
)

TModel = TypeVar("TModel", bound=StrictModel)
TStateModel = TypeVar(
    "TStateModel",
    PaperLedgerEntry,
    PositionLifecycleEvent,
    ReviewFollowup,
    TradeOutcome,
)
TTargetModel = TypeVar("TTargetModel", ReviewDecision, ReviewNote)


def _target_key(target_type: ReviewTargetType | str, target_id: str) -> str:
    resolved_target_type = target_type.value if isinstance(target_type, ReviewTargetType) else target_type
    return f"{resolved_target_type}::{target_id}"


class LoadedPaperLedgerWorkspace(StrictModel):
    """Typed bundle of persisted artifacts used by paper-ledger workflows."""

    paper_trades_by_id: dict[str, PaperTrade] = Field(default_factory=dict)
    paper_position_states_by_id: dict[str, PaperPositionState] = Field(default_factory=dict)
    paper_ledger_entries_by_state_id: dict[str, list[PaperLedgerEntry]] = Field(default_factory=dict)
    position_lifecycle_events_by_state_id: dict[str, list[PositionLifecycleEvent]] = Field(
        default_factory=dict
    )
    trade_outcomes_by_id: dict[str, TradeOutcome] = Field(default_factory=dict)
    trade_outcomes_by_state_id: dict[str, list[TradeOutcome]] = Field(default_factory=dict)
    outcome_attributions_by_outcome_id: dict[str, OutcomeAttribution] = Field(default_factory=dict)
    review_followups_by_state_id: dict[str, list[ReviewFollowup]] = Field(default_factory=dict)
    daily_paper_summaries: list[DailyPaperSummary] = Field(default_factory=list)
    portfolio_proposals_by_id: dict[str, PortfolioProposal] = Field(default_factory=dict)
    position_ideas_by_id: dict[str, PositionIdea] = Field(default_factory=dict)
    signals_by_id: dict[str, Signal] = Field(default_factory=dict)
    review_decisions_by_target_key: dict[str, list[ReviewDecision]] = Field(default_factory=dict)
    review_notes_by_target_key: dict[str, list[ReviewNote]] = Field(default_factory=dict)


def load_paper_ledger_workspace(
    *,
    portfolio_root: Path,
    signal_root: Path,
    review_root: Path,
) -> LoadedPaperLedgerWorkspace:
    """Load persisted portfolio, paper-ledger, and review artifacts needed by the ledger service."""

    paper_trades = _load_models(portfolio_root / "paper_trades", PaperTrade)
    paper_position_states = _load_models(portfolio_root / "paper_position_states", PaperPositionState)
    paper_ledger_entries = _load_models(portfolio_root / "paper_ledger_entries", PaperLedgerEntry)
    position_lifecycle_events = _load_models(
        portfolio_root / "position_lifecycle_events",
        PositionLifecycleEvent,
    )
    trade_outcomes = _load_models(portfolio_root / "trade_outcomes", TradeOutcome)
    outcome_attributions = _load_models(portfolio_root / "outcome_attributions", OutcomeAttribution)
    review_followups = _load_models(portfolio_root / "review_followups", ReviewFollowup)
    daily_paper_summaries = _load_models(portfolio_root / "daily_paper_summaries", DailyPaperSummary)
    portfolio_proposals = _load_models(portfolio_root / "portfolio_proposals", PortfolioProposal)
    position_ideas = _load_models(portfolio_root / "position_ideas", PositionIdea)
    signals = _load_models(signal_root / "signals", Signal)
    review_notes = _load_models(review_root / "review_notes", ReviewNote)
    review_decisions = _load_review_decisions(review_root=review_root, portfolio_root=portfolio_root)
    return LoadedPaperLedgerWorkspace(
        paper_trades_by_id={paper_trade.paper_trade_id: paper_trade for paper_trade in paper_trades},
        paper_position_states_by_id={
            paper_position_state.paper_position_state_id: paper_position_state
            for paper_position_state in paper_position_states
        },
        paper_ledger_entries_by_state_id=_group_by_state(paper_ledger_entries),
        position_lifecycle_events_by_state_id=_group_by_state(position_lifecycle_events),
        trade_outcomes_by_id={
            trade_outcome.trade_outcome_id: trade_outcome for trade_outcome in trade_outcomes
        },
        trade_outcomes_by_state_id=_group_by_state(trade_outcomes),
        outcome_attributions_by_outcome_id={
            attribution.trade_outcome_id: attribution for attribution in outcome_attributions
        },
        review_followups_by_state_id=_group_by_state(review_followups),
        daily_paper_summaries=daily_paper_summaries,
        portfolio_proposals_by_id={
            portfolio_proposal.portfolio_proposal_id: portfolio_proposal
            for portfolio_proposal in portfolio_proposals
        },
        position_ideas_by_id={position_idea.position_idea_id: position_idea for position_idea in position_ideas},
        signals_by_id={signal.signal_id: signal for signal in signals},
        review_decisions_by_target_key=_group_by_target(review_decisions),
        review_notes_by_target_key=_group_by_target(review_notes),
    )


def _load_models(directory: Path, model_cls: type[TModel]) -> list[TModel]:
    return load_local_models(directory, model_cls)


def _load_review_decisions(*, review_root: Path, portfolio_root: Path) -> list[ReviewDecision]:
    primary = {
        decision.review_decision_id: decision
        for decision in _load_models(review_root / "review_decisions", ReviewDecision)
    }
    for decision in _load_models(portfolio_root / "review_decisions", ReviewDecision):
        primary.setdefault(decision.review_decision_id, decision)
    return list(primary.values())


def _group_by_state(models: list[TStateModel]) -> dict[str, list[TStateModel]]:
    grouped: dict[str, list[TStateModel]] = {}
    for model in models:
        state_id = model.paper_position_state_id
        grouped.setdefault(state_id, []).append(model)
    for items in grouped.values():
        items.sort(key=lambda item: item.created_at)
    return grouped


def _group_by_target(models: list[TTargetModel]) -> dict[str, list[TTargetModel]]:
    grouped: dict[str, list[TTargetModel]] = {}
    for model in models:
        key = _target_key(model.target_type, model.target_id)
        grouped.setdefault(key, []).append(model)
    for items in grouped.values():
        items.sort(key=lambda item: item.created_at)
    return grouped
