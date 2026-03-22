from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar, cast

from libraries.schemas import (
    BacktestRun,
    CounterHypothesis,
    Document,
    EarningsCall,
    EvidenceAssessment,
    EvidenceSpan,
    Experiment,
    Filing,
    Hypothesis,
    Memo,
    NewsItem,
    PaperTrade,
    PortfolioProposal,
    ResearchBrief,
    ReviewNote,
    Signal,
    StrictModel,
)

TModel = TypeVar("TModel", bound=StrictModel)


@dataclass(frozen=True)
class StoredModel(Generic[TModel]):
    """One parsed persisted model plus its on-disk location."""

    model: TModel
    path: Path

    @property
    def uri(self) -> str:
        """Return the canonical local file URI for the stored model."""

        return self.path.resolve().as_uri()


@dataclass(frozen=True)
class ResolvedResearchMemoryRoots:
    """Resolved local roots used by the retrieval service."""

    workspace_root: Path
    research_root: Path
    parsing_root: Path
    ingestion_root: Path
    review_root: Path
    experiments_root: Path
    backtesting_root: Path
    signal_root: Path
    portfolio_root: Path


@dataclass(frozen=True)
class ResearchMemoryWorkspace:
    """In-memory view of persisted artifacts searchable by the retrieval layer."""

    roots: ResolvedResearchMemoryRoots
    documents: list[StoredModel[Document]]
    evidence_spans: list[StoredModel[EvidenceSpan]]
    evidence_assessments: list[StoredModel[EvidenceAssessment]]
    hypotheses: list[StoredModel[Hypothesis]]
    counter_hypotheses: list[StoredModel[CounterHypothesis]]
    research_briefs: list[StoredModel[ResearchBrief]]
    memos: list[StoredModel[Memo]]
    experiments: list[StoredModel[Experiment]]
    review_notes: list[StoredModel[ReviewNote]]
    signals: list[StoredModel[Signal]]
    portfolio_proposals: list[StoredModel[PortfolioProposal]]
    paper_trades: list[StoredModel[PaperTrade]]
    backtest_runs: list[StoredModel[BacktestRun]]


def resolve_research_memory_roots(
    *,
    workspace_root: Path,
    research_root: Path | None = None,
    parsing_root: Path | None = None,
    ingestion_root: Path | None = None,
    review_root: Path | None = None,
    experiments_root: Path | None = None,
    backtesting_root: Path | None = None,
) -> ResolvedResearchMemoryRoots:
    """Resolve the artifact roots searched by the read-only retrieval layer."""

    return ResolvedResearchMemoryRoots(
        workspace_root=workspace_root,
        research_root=research_root or (workspace_root / "research"),
        parsing_root=parsing_root or (workspace_root / "parsing"),
        ingestion_root=ingestion_root or (workspace_root / "ingestion"),
        review_root=review_root or (workspace_root / "review"),
        experiments_root=experiments_root or (workspace_root / "experiments"),
        backtesting_root=backtesting_root or (workspace_root / "backtesting"),
        signal_root=workspace_root / "signal_generation",
        portfolio_root=workspace_root / "portfolio",
    )


def load_research_memory_workspace(
    *,
    workspace_root: Path,
    research_root: Path | None = None,
    parsing_root: Path | None = None,
    ingestion_root: Path | None = None,
    review_root: Path | None = None,
    experiments_root: Path | None = None,
    backtesting_root: Path | None = None,
) -> ResearchMemoryWorkspace:
    """Load persisted artifacts needed for metadata-first retrieval."""

    roots = resolve_research_memory_roots(
        workspace_root=workspace_root,
        research_root=research_root,
        parsing_root=parsing_root,
        ingestion_root=ingestion_root,
        review_root=review_root,
        experiments_root=experiments_root,
        backtesting_root=backtesting_root,
    )
    return ResearchMemoryWorkspace(
        roots=roots,
        documents=_load_documents(roots.ingestion_root),
        evidence_spans=load_models(roots.parsing_root / "evidence_spans", EvidenceSpan),
        evidence_assessments=load_models(
            roots.research_root / "evidence_assessments",
            EvidenceAssessment,
        ),
        hypotheses=load_models(roots.research_root / "hypotheses", Hypothesis),
        counter_hypotheses=load_models(
            roots.research_root / "counter_hypotheses",
            CounterHypothesis,
        ),
        research_briefs=load_models(roots.research_root / "research_briefs", ResearchBrief),
        memos=load_models(roots.research_root / "memos", Memo),
        experiments=load_models(roots.experiments_root / "experiments", Experiment),
        review_notes=load_models(roots.review_root / "review_notes", ReviewNote),
        signals=load_models(roots.signal_root / "signals", Signal),
        portfolio_proposals=load_models(
            roots.portfolio_root / "portfolio_proposals",
            PortfolioProposal,
        ),
        paper_trades=load_models(roots.portfolio_root / "paper_trades", PaperTrade),
        backtest_runs=load_models(roots.backtesting_root / "runs", BacktestRun),
    )


def load_models(directory: Path, model_cls: type[TModel]) -> list[StoredModel[TModel]]:
    """Load persisted JSON models from one directory when it exists."""

    if not directory.exists():
        return []
    return [
        StoredModel(
            model=model_cls.model_validate_json(path.read_text(encoding="utf-8")),
            path=path,
        )
        for path in sorted(directory.glob("*.json"))
    ]


def _load_documents(ingestion_root: Path) -> list[StoredModel[Document]]:
    """Load normalized document records from the ingestion root."""

    normalized_root = ingestion_root / "normalized"
    return sorted(
        [
            *[
                cast(StoredModel[Document], StoredModel(model=stored.model, path=stored.path))
                for stored in load_models(normalized_root / "filings", Filing)
            ],
            *[
                cast(StoredModel[Document], StoredModel(model=stored.model, path=stored.path))
                for stored in load_models(normalized_root / "earnings_calls", EarningsCall)
            ],
            *[
                cast(StoredModel[Document], StoredModel(model=stored.model, path=stored.path))
                for stored in load_models(normalized_root / "news_items", NewsItem)
            ],
        ],
        key=lambda stored: stored.model.document_id,
    )
