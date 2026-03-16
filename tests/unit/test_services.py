from __future__ import annotations

from libraries.schemas import DocumentKind
from services.ingestion import DocumentIngestionRequest, IngestionService


def test_ingestion_service_imports_and_accepts_request() -> None:
    service = IngestionService()
    request = DocumentIngestionRequest(
        source_reference_id="src_test",
        document_kind=DocumentKind.FILING,
        title="Sample Filing",
        raw_text="sample payload",
        requested_by="unit_test",
    )

    response = service.ingest_document(request)

    assert response.status == "queued"
    assert response.document_id.startswith("doc_")
