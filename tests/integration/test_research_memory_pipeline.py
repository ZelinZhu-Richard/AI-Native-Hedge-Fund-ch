from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
    MemoryScope,
    RetrievalQuery,
    ReviewTargetType,
    SignalStatus,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.time import FrozenClock
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_backtest_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import run_feature_signal_pipeline
from services.operator_review import (
    AddReviewNoteRequest,
    GetReviewContextRequest,
    OperatorReviewService,
    SyncReviewQueueRequest,
)
from services.research_memory import ResearchMemoryService, SearchResearchMemoryRequest

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
INGEST_TIME = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)
FIRST_RESEARCH_TIME = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)
SIGNAL_TIME = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)
BACKTEST_TIME = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)
REVIEW_TIME = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
SECOND_RESEARCH_TIME = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)


def test_research_memory_retrieval_is_advisory_and_workflow_visible(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=artifact_root / "ingestion",
        clock=FrozenClock(INGEST_TIME),
    )
    run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=FrozenClock(INGEST_TIME),
    )

    first_research = run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(FIRST_RESEARCH_TIME),
    )
    assert first_research.research_brief is not None
    signal_pipeline = run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(SIGNAL_TIME),
    )
    run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        experiment_root=artifact_root / "experiments",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(BACKTEST_TIME),
    )

    review_service = OperatorReviewService(clock=FrozenClock(REVIEW_TIME))
    review_service.sync_review_queue(
        SyncReviewQueueRequest(
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
        )
    )
    review_service.add_review_note(
        AddReviewNoteRequest(
            target_type=ReviewTargetType.RESEARCH_BRIEF,
            target_id=first_research.research_brief.research_brief_id,
            author_id="reviewer_1",
            body="Preserve the open question about durability of demand recovery.",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
        )
    )

    second_research = run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(SECOND_RESEARCH_TIME),
    )

    assert second_research.retrieval_context is not None
    assert second_research.retrieval_context.semantic_retrieval_used is False
    assert second_research.retrieval_context.evidence_results
    assert any(
        result.artifact_reference.artifact_type == "Hypothesis"
        for result in second_research.retrieval_context.results
    )
    assert second_research.memo is not None
    assert any(
        note.startswith("retrieval_context_results=")
        for note in second_research.memo.provenance.notes
    )

    search_response = ResearchMemoryService(clock=FrozenClock(SECOND_RESEARCH_TIME)).search_research_memory(
        SearchResearchMemoryRequest(
            workspace_root=artifact_root,
            research_root=artifact_root / "research",
            parsing_root=artifact_root / "parsing",
            ingestion_root=artifact_root / "ingestion",
            review_root=artifact_root / "review",
            experiments_root=artifact_root / "experiments",
            backtesting_root=artifact_root / "backtesting",
            query=RetrievalQuery(
                retrieval_query_id="rqry_pipeline",
                scopes=[
                    MemoryScope.EVIDENCE,
                    MemoryScope.EVIDENCE_ASSESSMENT,
                    MemoryScope.HYPOTHESIS,
                    MemoryScope.COUNTER_HYPOTHESIS,
                    MemoryScope.RESEARCH_BRIEF,
                    MemoryScope.MEMO,
                    MemoryScope.EXPERIMENT,
                    MemoryScope.REVIEW_NOTE,
                ],
                company_id=first_research.company_id,
                limit=50,
            ),
        )
    )

    result_types = {
        result.artifact_reference.artifact_type for result in search_response.retrieval_context.results
    }
    assert {"Hypothesis", "CounterHypothesis", "ResearchBrief", "Memo", "Experiment", "ReviewNote"} <= result_types
    assert search_response.retrieval_context.evidence_results
    for retrieval_result in search_response.retrieval_context.results:
        assert _uri_exists(retrieval_result.artifact_reference.storage_uri)
    for evidence_result in search_response.retrieval_context.evidence_results:
        assert _uri_exists(evidence_result.artifact_reference.storage_uri)

    signal = signal_pipeline.signal_generation.signals[0]
    context = review_service.get_review_context(
        GetReviewContextRequest(
            target_type=ReviewTargetType.SIGNAL,
            target_id=signal.signal_id,
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            review_root=artifact_root / "review",
            audit_root=artifact_root / "audit",
        )
    )

    assert context.related_prior_work is not None
    related_types = {
        result.artifact_reference.artifact_type for result in context.related_prior_work.results
    }
    assert "ReviewNote" in related_types
    assert "Memo" in related_types


def _backtest_config() -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id(
            "btcfg",
            "text_only_candidate_signal",
            "2026-03-17",
            "2026-03-30",
            "5.0",
            "2.0",
        ),
        strategy_name="day6_text_signal_exploratory",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 30),
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", "5.0", "2.0", "lag1"),
            transaction_cost_bps=5.0,
            slippage_bps=2.0,
            execution_lag_bars=1,
            decision_price_field="close",
            execution_price_field="open",
            provenance=ProvenanceRecord(processing_time=BACKTEST_TIME),
            created_at=BACKTEST_TIME,
            updated_at=BACKTEST_TIME,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=ProvenanceRecord(processing_time=BACKTEST_TIME),
        created_at=BACKTEST_TIME,
        updated_at=BACKTEST_TIME,
    )


def _uri_exists(uri: str) -> bool:
    return Path(urlparse(uri).path).exists()
