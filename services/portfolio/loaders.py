from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.schemas import (
    BacktestRun,
    Company,
    EvidenceAssessment,
    Hypothesis,
    ResearchBrief,
    Signal,
    StrictModel,
)
from libraries.schemas.base import TimestampedModel

T = TypeVar("T", bound=TimestampedModel)


class LoadedPortfolioInputs(StrictModel):
    """Typed bundle of persisted artifacts used for Day 7 portfolio workflows."""

    company_id: str = Field(description="Covered company identifier.")
    company: Company | None = Field(
        default=None,
        description="Normalized company metadata used for symbol resolution when available.",
    )
    signals: list[Signal] = Field(
        default_factory=list,
        description="Persisted Day 5 candidate or approved signals for one company.",
    )
    hypotheses_by_id: dict[str, Hypothesis] = Field(
        default_factory=dict,
        description="Hypotheses keyed by identifier for position idea traceability.",
    )
    evidence_assessments_by_id: dict[str, EvidenceAssessment] = Field(
        default_factory=dict,
        description="Evidence assessments keyed by identifier for risk review.",
    )
    research_briefs_by_id: dict[str, ResearchBrief] = Field(
        default_factory=dict,
        description="Research briefs keyed by identifier for memo-ready position context.",
    )
    latest_backtest_run: BacktestRun | None = Field(
        default=None,
        description="Latest exploratory backtest run for the company when available.",
    )


def load_portfolio_inputs(
    *,
    signal_root: Path,
    research_root: Path,
    ingestion_root: Path | None,
    backtesting_root: Path | None,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
) -> LoadedPortfolioInputs:
    """Load persisted Day 5 and Day 6 artifacts needed for Day 7 workflows."""

    signals = _apply_signal_cutoff(
        _load_models(signal_root / "signals", Signal),
        as_of_time=as_of_time,
    )
    resolved_company_id = _resolve_company_id(company_id=company_id, signals=signals)
    company_signals = [signal for signal in signals if signal.company_id == resolved_company_id]
    if not company_signals:
        raise ValueError(f"No signals were found for `{resolved_company_id}`.")

    hypotheses = [
        hypothesis
        for hypothesis in _apply_created_at_cutoff(
            _load_models(research_root / "hypotheses", Hypothesis),
            as_of_time=as_of_time,
        )
        if hypothesis.company_id == resolved_company_id
    ]
    evidence_assessments = [
        assessment
        for assessment in _apply_created_at_cutoff(
            _load_models(research_root / "evidence_assessments", EvidenceAssessment),
            as_of_time=as_of_time,
        )
        if assessment.company_id == resolved_company_id
    ]
    research_briefs = [
        brief
        for brief in _apply_created_at_cutoff(
            _load_models(research_root / "research_briefs", ResearchBrief),
            as_of_time=as_of_time,
        )
        if brief.company_id == resolved_company_id
    ]

    company = None
    if ingestion_root is not None:
        company_path = ingestion_root / "normalized" / "companies" / f"{resolved_company_id}.json"
        if company_path.exists():
            loaded_company = Company.model_validate_json(company_path.read_text(encoding="utf-8"))
            if as_of_time is None or loaded_company.created_at <= as_of_time:
                company = loaded_company

    latest_backtest_run = None
    if backtesting_root is not None and (backtesting_root / "runs").exists():
        company_runs = [
            run
            for run in _apply_created_at_cutoff(
                _load_models(backtesting_root / "runs", BacktestRun),
                as_of_time=as_of_time,
            )
            if run.company_id == resolved_company_id
        ]
        if company_runs:
            latest_backtest_run = max(company_runs, key=lambda run: run.created_at)

    return LoadedPortfolioInputs(
        company_id=resolved_company_id,
        company=company,
        signals=sorted(
            company_signals,
            key=lambda signal: (
                signal.effective_at,
                abs(signal.primary_score),
                signal.signal_id,
            ),
            reverse=True,
        ),
        hypotheses_by_id={hypothesis.hypothesis_id: hypothesis for hypothesis in hypotheses},
        evidence_assessments_by_id={
            assessment.evidence_assessment_id: assessment for assessment in evidence_assessments
        },
        research_briefs_by_id={brief.research_brief_id: brief for brief in research_briefs},
        latest_backtest_run=latest_backtest_run,
    )


def _resolve_company_id(*, company_id: str | None, signals: list[Signal]) -> str:
    """Resolve a single company identifier from persisted signals."""

    available_company_ids = sorted({signal.company_id for signal in signals})
    if company_id is not None:
        if company_id not in available_company_ids:
            raise ValueError(f"Company `{company_id}` was not found under the signal root.")
        return company_id
    if len(available_company_ids) != 1:
        raise ValueError(
            "Portfolio workflows require an explicit company_id when signals contain zero or "
            "multiple companies."
        )
    return available_company_ids[0]


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from one category directory."""

    if not directory.exists():
        return []
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _apply_created_at_cutoff(
    artifacts: list[T],
    *,
    as_of_time: datetime | None,
) -> list[T]:
    """Apply an optional creation-time cutoff to persisted artifacts."""

    if as_of_time is None:
        return artifacts
    return [artifact for artifact in artifacts if artifact.created_at <= as_of_time]


def _apply_signal_cutoff(
    signals: list[Signal],
    *,
    as_of_time: datetime | None,
) -> list[Signal]:
    """Apply an optional point-in-time cutoff to persisted signals."""

    if as_of_time is None:
        return signals
    return [
        signal
        for signal in signals
        if signal.created_at <= as_of_time and signal.effective_at <= as_of_time
    ]
