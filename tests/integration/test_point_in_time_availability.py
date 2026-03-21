from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    ExecutionAssumption,
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
from pipelines.signal_generation import (
    FeatureSignalPipelineResponse,
    run_feature_signal_pipeline,
)
from services.backtesting import RunBacktestWorkflowResponse
from services.parsing import ExtractDocumentEvidenceResponse

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 25, 15, 0, tzinfo=UTC)


@dataclass(frozen=True)
class PointInTimeChainResult:
    parsing: list[ExtractDocumentEvidenceResponse]
    feature_signal: FeatureSignalPipelineResponse
    backtest: RunBacktestWorkflowResponse


def test_point_in_time_document_availability_controls_signal_and_backtest_timing(
    tmp_path: Path,
) -> None:
    pre_market_result = _run_point_in_time_chain(
        tmp_path=tmp_path,
        run_name="pre_market",
        published_at="2026-03-18T08:15:00-04:00",
        retrieved_at="2026-03-18T12:20:00Z",
    )
    after_hours_result = _run_point_in_time_chain(
        tmp_path=tmp_path,
        run_name="after_hours",
        published_at="2026-03-18T17:15:00-04:00",
        retrieved_at="2026-03-18T21:30:00Z",
    )

    pre_parsing_response = pre_market_result.parsing[0]
    assert pre_parsing_response.publication_timing is not None
    assert pre_parsing_response.availability_window is not None
    assert pre_parsing_response.publication_timing.internal_available_at == datetime(
        2026,
        3,
        18,
        13,
        30,
        tzinfo=UTC,
    )
    assert not pre_parsing_response.timing_anomalies

    after_parsing_response = after_hours_result.parsing[0]
    assert after_parsing_response.publication_timing is not None
    assert after_parsing_response.availability_window is not None
    assert after_parsing_response.publication_timing.internal_available_at == datetime(
        2026,
        3,
        19,
        13,
        30,
        tzinfo=UTC,
    )
    assert not after_parsing_response.timing_anomalies

    pre_signal = pre_market_result.feature_signal.signal_generation.signals[0]
    after_signal = after_hours_result.feature_signal.signal_generation.signals[0]
    assert pre_signal.availability_window is not None
    assert after_signal.availability_window is not None
    assert pre_signal.effective_at == datetime(2026, 3, 18, 13, 30, tzinfo=UTC)
    assert after_signal.effective_at == datetime(2026, 3, 19, 13, 30, tzinfo=UTC)

    pre_backtest = pre_market_result.backtest
    after_backtest = after_hours_result.backtest
    assert pre_backtest.decision_cutoffs
    assert after_backtest.decision_cutoffs

    pre_first_signal_time = min(
        decision.decision_time
        for decision in pre_backtest.strategy_decisions
        if decision.signal_id is not None
    )
    after_first_signal_time = min(
        decision.decision_time
        for decision in after_backtest.strategy_decisions
        if decision.signal_id is not None
    )
    assert pre_first_signal_time == datetime(2026, 3, 18, 20, 0, tzinfo=UTC)
    assert after_first_signal_time == datetime(2026, 3, 19, 20, 0, tzinfo=UTC)
    assert all(
        decision.signal_id is None
        for decision in after_backtest.strategy_decisions
        if decision.decision_time < datetime(2026, 3, 19, 20, 0, tzinfo=UTC)
    )
    assert all(
        decision.signal_effective_at is None
        or decision.signal_effective_at <= decision.decision_time
        for decision in pre_backtest.strategy_decisions + after_backtest.strategy_decisions
    )


def _run_point_in_time_chain(
    *,
    tmp_path: Path,
    run_name: str,
    published_at: str,
    retrieved_at: str,
) -> PointInTimeChainResult:
    fixture_root = _build_fixture_root(
        tmp_path=tmp_path,
        run_name=run_name,
        published_at=published_at,
        retrieved_at=retrieved_at,
    )
    artifact_root = tmp_path / "artifacts" / run_name

    run_fixture_ingestion_pipeline(
        fixtures_root=fixture_root,
        output_root=artifact_root / "ingestion",
        clock=FrozenClock(FIXED_NOW),
    )
    parsing_responses = run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=FrozenClock(FIXED_NOW),
    )
    run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(FIXED_NOW),
    )
    feature_signal_response = run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(FIXED_NOW),
    )
    backtest_response = run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=FrozenClock(FIXED_NOW),
    )
    return PointInTimeChainResult(
        parsing=parsing_responses,
        feature_signal=feature_signal_response,
        backtest=backtest_response,
    )


def _build_fixture_root(
    *,
    tmp_path: Path,
    run_name: str,
    published_at: str,
    retrieved_at: str,
) -> Path:
    fixture_root = tmp_path / "fixtures" / run_name
    for category in ("companies", "market_data", "filings", "news", "transcripts"):
        (fixture_root / category).mkdir(parents=True, exist_ok=True)

    for category, filename in (
        ("companies", "apex_company_reference.json"),
        ("market_data", "apex_price_series_metadata.json"),
    ):
        shutil.copy2(FIXTURE_ROOT / category / filename, fixture_root / category / filename)

    filing_payload = json.loads(
        (FIXTURE_ROOT / "filings" / "apex_q1_2026_10q.json").read_text(encoding="utf-8")
    )
    filing_payload["published_at"] = published_at
    filing_payload["retrieved_at"] = retrieved_at
    filing_payload["uri"] = filing_payload["uri"].replace("20260507", run_name)
    filing_payload["external_id"] = f"{filing_payload['external_id']}-{run_name}"
    (fixture_root / "filings" / "apex_q1_2026_10q.json").write_text(
        json.dumps(filing_payload, indent=2),
        encoding="utf-8",
    )

    news_payload = json.loads(
        (FIXTURE_ROOT / "news" / "apex_launch_news.json").read_text(encoding="utf-8")
    )
    news_payload["published_at"] = published_at
    news_payload["retrieved_at"] = retrieved_at
    news_payload["uri"] = news_payload["uri"].replace("20260509", run_name)
    news_payload["external_id"] = f"{news_payload['external_id']}-{run_name}"
    (fixture_root / "news" / "apex_launch_news.json").write_text(
        json.dumps(news_payload, indent=2),
        encoding="utf-8",
    )

    transcript_payload = json.loads(
        (FIXTURE_ROOT / "transcripts" / "apex_q1_2026_call.json").read_text(encoding="utf-8")
    )
    transcript_payload["published_at"] = published_at
    transcript_payload["retrieved_at"] = retrieved_at
    transcript_payload["call_datetime"] = (
        "2026-03-17T16:30:00-04:00"
        if run_name == "pre_market"
        else "2026-03-18T16:30:00-04:00"
    )
    transcript_payload["uri"] = transcript_payload["uri"].replace("q1-2026", run_name)
    transcript_payload["external_id"] = f"{transcript_payload['external_id']}-{run_name}"
    (fixture_root / "transcripts" / "apex_q1_2026_call.json").write_text(
        json.dumps(transcript_payload, indent=2),
        encoding="utf-8",
    )
    return fixture_root


def _backtest_config() -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id(
            "btcfg",
            "text_only_candidate_signal",
            "2026-03-17",
            "2026-03-20",
            "5.0",
            "2.0",
        ),
        strategy_name="day6_text_signal_exploratory",
        signal_family="text_only_candidate_signal",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 17),
        test_end=date(2026, 3, 20),
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", "5.0", "2.0", "lag1"),
            transaction_cost_bps=5.0,
            slippage_bps=2.0,
            execution_lag_bars=1,
            decision_price_field="close",
            execution_price_field="open",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
