from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import TimingAnomalyKind
from libraries.time import FrozenClock
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"


def test_evidence_extraction_pipeline_processes_parseable_documents(tmp_path: Path) -> None:
    ingestion_root = tmp_path / "ingestion"
    parsing_root = tmp_path / "parsing"

    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=ingestion_root,
        clock=FrozenClock(datetime(2026, 3, 16, 14, 30, tzinfo=UTC)),
    )
    responses = run_evidence_extraction_pipeline(
        ingestion_root=ingestion_root,
        output_root=parsing_root,
        clock=FrozenClock(datetime(2026, 3, 16, 14, 30, tzinfo=UTC)),
    )

    assert len(responses) == 3
    assert all(response.segments for response in responses)
    assert all(response.evidence_spans for response in responses)
    assert all(response.evaluation.passed for response in responses)
    assert all(response.publication_timing is not None for response in responses)
    assert all(response.availability_window is not None for response in responses)
    assert all(
        response.publication_timing.internal_available_at
        == response.availability_window.available_from
        for response in responses
        if response.publication_timing is not None and response.availability_window is not None
    )
    assert all(
        {
            anomaly.anomaly_kind for anomaly in response.timing_anomalies
        }.issubset({TimingAnomalyKind.INGESTED_BEFORE_PUBLICATION})
        for response in responses
    )
    assert (parsing_root / "parsed_text").exists()
    assert (parsing_root / "segments").exists()
    assert (parsing_root / "evidence_spans").exists()
    assert (parsing_root / "claims").exists()
