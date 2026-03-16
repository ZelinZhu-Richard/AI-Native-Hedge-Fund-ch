from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import StrictModel
from libraries.utils import make_prefixed_id


class ParseDocumentRequest(StrictModel):
    """Request to normalize and extract structured artifacts from a document."""

    document_id: str = Field(description="Document to parse.")
    parse_mode: str = Field(default="full", description="Requested parsing mode.")
    requested_by: str = Field(description="Requester identifier.")


class ParseDocumentResponse(StrictModel):
    """Response returned after accepting a parse request."""

    parse_run_id: str = Field(description="Identifier for the parse run.")
    document_id: str = Field(description="Document being parsed.")
    status: str = Field(description="Operational status.")
    accepted_at: datetime = Field(description="UTC timestamp when the request was accepted.")
    expected_artifacts: list[str] = Field(
        default_factory=list,
        description="Artifacts expected from the parse run.",
    )


class ParsingService(BaseService):
    """Normalize documents and extract evidence-bearing structured artifacts."""

    capability_name = "parsing"
    capability_description = "Normalizes source documents and extracts structured evidence."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Document"],
            produces=["EvidenceSpan", "normalized text", "ParseDocumentResponse"],
            api_routes=[],
        )

    def parse_document(self, request: ParseDocumentRequest) -> ParseDocumentResponse:
        """Accept a document for parsing."""

        return ParseDocumentResponse(
            parse_run_id=make_prefixed_id("parse"),
            document_id=request.document_id,
            status="queued",
            accepted_at=self.clock.now(),
            expected_artifacts=["EvidenceSpan", "normalized_text"],
        )
