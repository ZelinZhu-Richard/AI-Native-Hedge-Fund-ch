from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.time import FrozenClock
from libraries.utils import make_company_id
from services.ingestion import FixtureIngestionRequest, IngestionService
from services.ingestion.fixture_loader import discover_raw_fixture_paths, load_fixture_record
from services.ingestion.normalization import normalize_raw_fixture

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"


def test_fixture_loader_discovers_expected_sample_set() -> None:
    paths = discover_raw_fixture_paths(FIXTURE_ROOT)

    assert len(paths) == 5
    assert {path.parent.name for path in paths} == {
        "companies",
        "filings",
        "market_data",
        "news",
        "transcripts",
    }


def test_normalize_filing_fixture_preserves_timestamps_and_provenance() -> None:
    fixture_path = FIXTURE_ROOT / "filings" / "apex_q1_2026_10q.json"
    record = load_fixture_record(fixture_path)
    fixed_now = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)

    normalized = normalize_raw_fixture(
        record.payload,
        clock=FrozenClock(fixed_now),
        fixture_path=str(fixture_path),
    )

    assert normalized.company is not None
    assert normalized.filing is not None
    assert normalized.company.company_id == make_company_id(
        legal_name="Apex Instruments, Inc.",
        cik="0001983210",
        ticker="APEX",
        country_of_risk="US",
    )
    assert normalized.source_reference.published_at == datetime(
        2026, 5, 7, 20, 15, tzinfo=UTC
    )
    assert normalized.source_reference.retrieved_at == datetime(
        2026, 5, 7, 20, 20, 10, tzinfo=UTC
    )
    assert normalized.filing.ingested_at == fixed_now
    assert normalized.filing.source_published_at == normalized.source_reference.published_at
    assert normalized.filing.provenance.source_reference_ids == [
        normalized.source_reference.source_reference_id
    ]
    assert normalized.source_reference.provenance.transformation_name == (
        "source_reference_normalization"
    )
    assert any(note.startswith("fixture_path=") for note in normalized.filing.provenance.notes)


def test_company_fixture_uses_as_of_time_as_effective_time() -> None:
    fixture_path = FIXTURE_ROOT / "companies" / "apex_company_reference.json"
    record = load_fixture_record(fixture_path)
    fixed_now = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)

    normalized = normalize_raw_fixture(
        record.payload,
        clock=FrozenClock(fixed_now),
        fixture_path=str(fixture_path),
    )

    assert normalized.company is not None
    assert normalized.source_reference.effective_at == datetime(2026, 5, 6, 0, 0, tzinfo=UTC)


def test_ingestion_service_persists_raw_and_normalized_artifacts(tmp_path: Path) -> None:
    fixture_path = FIXTURE_ROOT / "filings" / "apex_q1_2026_10q.json"
    record = load_fixture_record(fixture_path)
    fixed_now = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)
    service = IngestionService(clock=FrozenClock(fixed_now))

    response = service.ingest_fixture(
        FixtureIngestionRequest(
            fixture_path=fixture_path,
            output_root=tmp_path,
            requested_by="unit_test",
        )
    )

    assert response.filing is not None
    assert response.company is not None
    assert len(response.storage_locations) == 4

    raw_path = tmp_path / "raw" / "filing" / f"{response.source_reference.source_reference_id}.json"
    source_reference_path = (
        tmp_path
        / "normalized"
        / "source_references"
        / f"{response.source_reference.source_reference_id}.json"
    )
    company_path = tmp_path / "normalized" / "companies" / f"{response.company.company_id}.json"
    filing_path = tmp_path / "normalized" / "filings" / f"{response.filing.document_id}.json"

    assert raw_path.read_text(encoding="utf-8") == record.raw_text
    assert source_reference_path.exists()
    assert company_path.exists()
    assert filing_path.exists()
