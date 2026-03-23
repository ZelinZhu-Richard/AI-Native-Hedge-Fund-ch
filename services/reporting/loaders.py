from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeVar, cast

from pydantic import Field

from libraries.core import load_local_models
from libraries.schemas import (
    DailySystemReport,
    ExperimentScorecard,
    ProposalScorecard,
    ResearchSummary,
    ReviewQueueSummary,
    RiskSummary,
    StrictModel,
    SystemCapabilitySummary,
)

TModel = TypeVar("TModel", bound=StrictModel)


class _CreatedAtModel(Protocol):
    created_at: datetime


class LoadedReportingWorkspace(StrictModel):
    """Typed bundle of persisted reporting artifacts."""

    research_summaries_by_brief_id: dict[str, list[ResearchSummary]] = Field(default_factory=dict)
    risk_summaries_by_proposal_id: dict[str, list[RiskSummary]] = Field(default_factory=dict)
    proposal_scorecards_by_proposal_id: dict[str, list[ProposalScorecard]] = Field(
        default_factory=dict
    )
    experiment_scorecards_by_experiment_id: dict[str, list[ExperimentScorecard]] = Field(
        default_factory=dict
    )
    review_queue_summaries: list[ReviewQueueSummary] = Field(default_factory=list)
    daily_system_reports: list[DailySystemReport] = Field(default_factory=list)
    system_capability_summaries_by_name: dict[str, list[SystemCapabilitySummary]] = Field(
        default_factory=dict
    )


def load_reporting_workspace(reporting_root: Path) -> LoadedReportingWorkspace:
    """Load persisted reporting artifacts when present."""

    research_summaries = _load_models(reporting_root / "research_summaries", ResearchSummary)
    risk_summaries = _load_models(reporting_root / "risk_summaries", RiskSummary)
    proposal_scorecards = _load_models(reporting_root / "proposal_scorecards", ProposalScorecard)
    experiment_scorecards = _load_models(
        reporting_root / "experiment_scorecards",
        ExperimentScorecard,
    )
    review_queue_summaries = _sorted_newest_first(
        _load_models(reporting_root / "review_queue_summaries", ReviewQueueSummary)
    )
    daily_system_reports = _sorted_newest_first(
        _load_models(reporting_root / "daily_system_reports", DailySystemReport)
    )
    capability_summaries = _load_models(
        reporting_root / "system_capability_summaries",
        SystemCapabilitySummary,
    )
    return LoadedReportingWorkspace(
        research_summaries_by_brief_id=_group_by_attr(research_summaries, "research_brief_id"),
        risk_summaries_by_proposal_id=_group_by_attr(risk_summaries, "portfolio_proposal_id"),
        proposal_scorecards_by_proposal_id=_group_by_attr(
            proposal_scorecards,
            "portfolio_proposal_id",
        ),
        experiment_scorecards_by_experiment_id=_group_by_attr(
            experiment_scorecards,
            "experiment_id",
        ),
        review_queue_summaries=review_queue_summaries,
        daily_system_reports=daily_system_reports,
        system_capability_summaries_by_name=_group_by_attr(
            capability_summaries,
            "capability_name",
        ),
    )


def latest_research_summary(
    workspace: LoadedReportingWorkspace, research_brief_id: str
) -> ResearchSummary | None:
    """Return the latest persisted research summary for one brief."""

    return _latest(workspace.research_summaries_by_brief_id.get(research_brief_id))


def latest_risk_summary(
    workspace: LoadedReportingWorkspace, portfolio_proposal_id: str
) -> RiskSummary | None:
    """Return the latest persisted risk summary for one proposal."""

    return _latest(workspace.risk_summaries_by_proposal_id.get(portfolio_proposal_id))


def latest_proposal_scorecard(
    workspace: LoadedReportingWorkspace, portfolio_proposal_id: str
) -> ProposalScorecard | None:
    """Return the latest persisted proposal scorecard for one proposal."""

    return _latest(workspace.proposal_scorecards_by_proposal_id.get(portfolio_proposal_id))


def _load_models(directory: Path, model_cls: type[TModel]) -> list[TModel]:
    return load_local_models(directory, model_cls)


def _sorted_newest_first(models: list[TModel]) -> list[TModel]:
    return sorted(models, key=_created_at, reverse=True)


def _group_by_attr(models: list[TModel], attribute_name: str) -> dict[str, list[TModel]]:
    grouped: dict[str, list[TModel]] = {}
    for model in models:
        attribute_value = getattr(model, attribute_name)
        grouped.setdefault(attribute_value, []).append(model)
    for items in grouped.values():
        sortable_items = items
        sortable_items.sort(key=lambda model: _created_at(model), reverse=True)
    return grouped


def _latest(models: list[TModel] | None) -> TModel | None:
    if not models:
        return None
    return models[0]


def _created_at(model: TModel) -> datetime:
    created_model = model
    return _as_created_at_model(created_model).created_at


def _as_created_at_model(model: TModel) -> _CreatedAtModel:
    return cast(_CreatedAtModel, model)
