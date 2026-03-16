from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import DocumentKind, StrictModel
from libraries.utils import make_prefixed_id


class DocumentIngestionRequest(StrictModel):
    """Request to register raw content for later normalization and parsing."""

    source_reference_id: str = Field(description="Source reference backing the ingestion request.")
    document_kind: DocumentKind = Field(description="Canonical document category.")
    title: str = Field(description="Proposed document title.")
    company_id: str | None = Field(
        default=None, description="Associated company identifier when applicable."
    )
    payload_uri: str | None = Field(
        default=None, description="URI to source payload when externally stored."
    )
    raw_text: str | None = Field(
        default=None, description="Inline raw text for local or fixture ingestion."
    )
    source_published_at: datetime | None = Field(
        default=None,
        description="UTC time the source content became visible upstream.",
    )
    requested_by: str = Field(description="Requester identifier.")

    @model_validator(mode="after")
    def validate_payload(self) -> DocumentIngestionRequest:
        """Require either a URI or inline text."""

        if not self.payload_uri and not self.raw_text:
            raise ValueError("Either payload_uri or raw_text must be provided.")
        return self


class DocumentIngestionResponse(StrictModel):
    """Response returned when a document ingestion request is accepted."""

    ingestion_job_id: str = Field(description="Identifier for the queued ingestion job.")
    document_id: str = Field(description="Reserved canonical document identifier.")
    status: str = Field(description="Operational status for the request.")
    queued_at: datetime = Field(description="UTC timestamp when the request was queued.")
    notes: list[str] = Field(
        default_factory=list, description="Operational notes for the requester."
    )


class IngestionService(BaseService):
    """Register and queue raw document content for the research platform."""

    capability_name = "ingestion"
    capability_description = "Registers raw source artifacts and queues normalization/parsing."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["SourceReference", "raw payload"],
            produces=["DocumentIngestionResponse", "Document"],
            api_routes=["POST /documents/ingest"],
        )

    def ingest_document(self, request: DocumentIngestionRequest) -> DocumentIngestionResponse:
        """Queue a document for later downstream processing."""

        queued_at = self.clock.now()
        return DocumentIngestionResponse(
            ingestion_job_id=make_prefixed_id("ingest"),
            document_id=make_prefixed_id("doc"),
            status="queued",
            queued_at=queued_at,
            notes=[f"Accepted for {request.document_kind.value} ingestion."],
        )
