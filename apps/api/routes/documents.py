from __future__ import annotations

from fastapi import APIRouter

from apps.api.builders import build_response_envelope
from apps.api.state import api_clock, service_registry
from libraries.schemas import APIResponseEnvelope
from services.ingestion import DocumentIngestionRequest, DocumentIngestionResponse, IngestionService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=APIResponseEnvelope[DocumentIngestionResponse])
def ingest_document(
    request: DocumentIngestionRequest,
) -> APIResponseEnvelope[DocumentIngestionResponse]:
    """Queue a document for future ingestion and normalization."""

    service = service_registry["ingestion"]
    assert isinstance(service, IngestionService)
    response = service.ingest_document(request)
    return build_response_envelope(data=response, generated_at=api_clock.now())
