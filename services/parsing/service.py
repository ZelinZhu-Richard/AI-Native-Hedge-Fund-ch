from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    DataLayer,
    DocumentEvidenceBundle,
    StrictModel,
)
from libraries.utils import make_prefixed_id
from services.parsing.extraction import build_document_evidence_bundle
from services.parsing.loaders import load_parsing_inputs
from services.parsing.segmentation import build_parsed_document_text, segment_document
from services.parsing.storage import LocalParsingArtifactStore


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


class ExtractDocumentEvidenceRequest(StrictModel):
    """Explicit local request for deterministic evidence extraction from stored artifacts."""

    document_path: Path = Field(description="Path to the normalized document JSON artifact.")
    source_reference_path: Path = Field(description="Path to the normalized source reference JSON.")
    raw_payload_path: Path = Field(description="Path to the exact raw source payload JSON.")
    output_root: Path | None = Field(
        default=None,
        description="Optional parsing artifact root. Defaults to the configured artifact root.",
    )
    requested_by: str = Field(description="Requester identifier.")


class ExtractDocumentEvidenceResponse(DocumentEvidenceBundle):
    """Evidence bundle plus storage metadata for a local parsing run."""

    extraction_run_id: str = Field(description="Identifier for the local extraction run.")
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the parsing flow.",
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
            consumes=["Document", "SourceReference", "raw payload"],
            produces=[
                "ParsedDocumentText",
                "DocumentSegment",
                "EvidenceSpan",
                "ExtractedClaim",
                "GuidanceChange",
                "ExtractDocumentEvidenceResponse",
            ],
            api_routes=[],
        )

    def parse_document(self, request: ParseDocumentRequest) -> ParseDocumentResponse:
        """Accept a document for parsing."""

        return ParseDocumentResponse(
            parse_run_id=make_prefixed_id("parse"),
            document_id=request.document_id,
            status="queued",
            accepted_at=self.clock.now(),
            expected_artifacts=[
                "ParsedDocumentText",
                "DocumentSegment",
                "EvidenceSpan",
                "ExtractedClaim",
                "GuidanceChange",
            ],
        )

    def extract_document_evidence(
        self,
        request: ExtractDocumentEvidenceRequest,
    ) -> ExtractDocumentEvidenceResponse:
        """Execute deterministic evidence extraction from explicit local artifacts."""

        extraction_run_id = make_prefixed_id("parse")
        notes = [
            f"document_path={request.document_path}",
            f"source_reference_path={request.source_reference_path}",
            f"raw_payload_path={request.raw_payload_path}",
        ]
        inputs = load_parsing_inputs(
            document_path=request.document_path,
            source_reference_path=request.source_reference_path,
            raw_payload_path=request.raw_payload_path,
        )
        parsed_document_text = build_parsed_document_text(
            inputs=inputs,
            clock=self.clock,
            workflow_run_id=extraction_run_id,
            notes=notes,
        )
        segments = segment_document(
            parsed_document_text=parsed_document_text,
            inputs=inputs,
            clock=self.clock,
            workflow_run_id=extraction_run_id,
            notes=notes,
        )
        bundle = build_document_evidence_bundle(
            parsed_document_text=parsed_document_text,
            segments=segments,
            inputs=inputs,
            clock=self.clock,
            workflow_run_id=extraction_run_id,
            notes=notes,
        )

        output_root = request.output_root
        if output_root is None:
            output_root = get_settings().resolved_artifact_root / "parsing"
        store = LocalParsingArtifactStore(root=output_root, clock=self.clock)
        storage_locations = self._persist_bundle(store=store, bundle=bundle)
        return ExtractDocumentEvidenceResponse(
            extraction_run_id=extraction_run_id,
            storage_locations=storage_locations,
            document_id=bundle.document_id,
            source_reference_id=bundle.source_reference_id,
            company_id=bundle.company_id,
            document_kind=bundle.document_kind,
            parsed_document_text=bundle.parsed_document_text,
            segments=bundle.segments,
            evidence_spans=bundle.evidence_spans,
            claims=bundle.claims,
            risk_factors=bundle.risk_factors,
            guidance_changes=bundle.guidance_changes,
            tone_markers=bundle.tone_markers,
            evaluation=bundle.evaluation,
        )

    def _persist_bundle(
        self,
        *,
        store: LocalParsingArtifactStore,
        bundle: DocumentEvidenceBundle,
    ) -> list[ArtifactStorageLocation]:
        """Persist parser-owned artifacts from a document evidence bundle."""

        source_reference_ids = [bundle.source_reference_id]
        storage_locations = [
            store.persist_model(
                artifact_id=bundle.parsed_document_text.parsed_document_text_id,
                category="parsed_text",
                model=bundle.parsed_document_text,
                data_layer=DataLayer.NORMALIZED,
                source_reference_ids=source_reference_ids,
            )
        ]
        for segment in bundle.segments:
            storage_locations.append(
                store.persist_model(
                    artifact_id=segment.document_segment_id,
                    category="segments",
                    model=segment,
                    data_layer=DataLayer.NORMALIZED,
                    source_reference_ids=source_reference_ids,
                )
            )
        for evidence_span in bundle.evidence_spans:
            storage_locations.append(
                store.persist_model(
                    artifact_id=evidence_span.evidence_span_id,
                    category="evidence_spans",
                    model=evidence_span,
                    data_layer=DataLayer.DERIVED,
                    source_reference_ids=source_reference_ids,
                )
            )
        for claim in bundle.claims:
            storage_locations.append(
                store.persist_model(
                    artifact_id=claim.extracted_claim_id,
                    category="claims",
                    model=claim,
                    data_layer=DataLayer.DERIVED,
                    source_reference_ids=source_reference_ids,
                )
            )
        for risk_factor in bundle.risk_factors:
            storage_locations.append(
                store.persist_model(
                    artifact_id=risk_factor.risk_factor_id,
                    category="risk_factors",
                    model=risk_factor,
                    data_layer=DataLayer.DERIVED,
                    source_reference_ids=source_reference_ids,
                )
            )
        for guidance_change in bundle.guidance_changes:
            storage_locations.append(
                store.persist_model(
                    artifact_id=guidance_change.guidance_change_id,
                    category="guidance_changes",
                    model=guidance_change,
                    data_layer=DataLayer.DERIVED,
                    source_reference_ids=source_reference_ids,
                )
            )
        for tone_marker in bundle.tone_markers:
            storage_locations.append(
                store.persist_model(
                    artifact_id=tone_marker.tone_marker_id,
                    category="tone_markers",
                    model=tone_marker,
                    data_layer=DataLayer.DERIVED,
                    source_reference_ids=source_reference_ids,
                )
            )
        return storage_locations
