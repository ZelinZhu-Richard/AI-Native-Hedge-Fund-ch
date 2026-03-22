from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from libraries.time import FrozenClock
from pipelines.document_processing import run_fixture_ingestion_pipeline

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"


def test_fixture_ingestion_pipeline_processes_sample_dataset(tmp_path: Path) -> None:
    responses = run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=tmp_path,
        clock=FrozenClock(datetime(2026, 3, 16, 14, 30, tzinfo=UTC)),
    )

    assert len(responses) == 5
    assert any(response.filing is not None for response in responses)
    assert any(response.earnings_call is not None for response in responses)
    assert any(response.news_item is not None for response in responses)
    assert any(response.price_series_metadata is not None for response in responses)
    assert len(
        {response.company.company_id for response in responses if response.company is not None}
    ) == 1


def test_fixture_ingestion_pipeline_requires_existing_fixture_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fixtures root"):
        run_fixture_ingestion_pipeline(
            fixtures_root=tmp_path / "missing_fixtures",
            output_root=tmp_path / "ingestion",
            clock=FrozenClock(datetime(2026, 3, 16, 14, 30, tzinfo=UTC)),
        )
