from __future__ import annotations

from pathlib import Path

from libraries.config import get_settings
from libraries.time import Clock, SystemClock
from services.parsing import (
    ExtractDocumentEvidenceRequest,
    ExtractDocumentEvidenceResponse,
    ParsingService,
)
from services.parsing.loaders import (
    discover_parseable_document_paths,
    load_parseable_document,
    resolve_raw_payload_path,
    resolve_source_reference_path,
)


def run_evidence_extraction_pipeline(
    *,
    ingestion_root: Path | None = None,
    output_root: Path | None = None,
    requested_by: str = "pipeline_evidence_extraction",
    clock: Clock | None = None,
) -> list[ExtractDocumentEvidenceResponse]:
    """Run deterministic evidence extraction over normalized Day 2 artifacts."""

    settings = get_settings()
    resolved_ingestion_root = ingestion_root or (settings.resolved_artifact_root / "ingestion")
    resolved_output_root = output_root or (settings.resolved_artifact_root / "parsing")
    service = ParsingService(clock=clock or SystemClock())

    responses: list[ExtractDocumentEvidenceResponse] = []
    for document_path in discover_parseable_document_paths(resolved_ingestion_root):
        document = load_parseable_document(document_path)
        responses.append(
            service.extract_document_evidence(
                ExtractDocumentEvidenceRequest(
                    document_path=document_path,
                    source_reference_path=resolve_source_reference_path(
                        ingestion_root=resolved_ingestion_root,
                        source_reference_id=document.source_reference_id,
                    ),
                    raw_payload_path=resolve_raw_payload_path(
                        ingestion_root=resolved_ingestion_root,
                        document_kind=document.kind,
                        source_reference_id=document.source_reference_id,
                    ),
                    output_root=resolved_output_root,
                    requested_by=requested_by,
                )
            )
        )
    return responses
