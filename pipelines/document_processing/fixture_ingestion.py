from __future__ import annotations

from pathlib import Path

from libraries.core import ensure_directory_exists
from libraries.time import Clock, SystemClock
from services.ingestion import FixtureIngestionRequest, FixtureIngestionResponse, IngestionService
from services.ingestion.fixture_loader import discover_raw_fixture_paths


def run_fixture_ingestion_pipeline(
    *,
    fixtures_root: Path,
    output_root: Path | None = None,
    requested_by: str = "pipeline_fixture_ingestion",
    clock: Clock | None = None,
) -> list[FixtureIngestionResponse]:
    """Run the local fixture ingestion pipeline over a fixture directory."""

    resolved_fixtures_root = ensure_directory_exists(fixtures_root, label="fixtures root")
    fixture_paths = discover_raw_fixture_paths(resolved_fixtures_root)
    if not fixture_paths:
        raise ValueError(f"No fixture JSON files were found under `{resolved_fixtures_root}`.")

    service = IngestionService(clock=clock or SystemClock())
    responses: list[FixtureIngestionResponse] = []
    for fixture_path in fixture_paths:
        responses.append(
            service.ingest_fixture(
                FixtureIngestionRequest(
                    fixture_path=fixture_path,
                    output_root=output_root,
                    requested_by=requested_by,
                )
            )
        )
    return responses
