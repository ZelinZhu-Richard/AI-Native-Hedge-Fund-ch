from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field, model_validator

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    DocumentKind,
    EarningsCall,
    Filing,
    NewsItem,
    StrictModel,
)
from libraries.utils import make_prefixed_id
from services.ingestion.fixture_loader import load_fixture_record
from services.ingestion.normalization import FixtureNormalizationResult, normalize_raw_fixture
from services.ingestion.storage import LocalArtifactStore


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


class FixtureIngestionRequest(StrictModel):
    """Request to ingest and normalize a local source fixture."""

    fixture_path: Path = Field(description="Path to the raw fixture file.")
    output_root: Path | None = Field(
        default=None,
        description="Optional artifact output root. Defaults to the configured artifact root.",
    )
    persist_raw: bool = Field(default=True, description="Whether to persist the raw fixture payload.")
    persist_normalized: bool = Field(
        default=True,
        description="Whether to persist normalized canonical artifacts.",
    )
    requested_by: str = Field(description="Requester identifier.")


class FixtureIngestionResponse(FixtureNormalizationResult):
    """Normalized artifacts and storage metadata produced from a fixture ingestion."""

    ingestion_job_id: str = Field(description="Identifier for the fixture ingestion run.")
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the ingestion flow.",
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
            consumes=["SourceReference", "raw payload", "local ingestion fixture"],
            produces=["DocumentIngestionResponse", "Document", "FixtureIngestionResponse"],
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

    def ingest_fixture(self, request: FixtureIngestionRequest) -> FixtureIngestionResponse:
        """Load, normalize, and optionally persist a local fixture-backed source payload."""

        fixture_record = load_fixture_record(request.fixture_path)
        normalized = normalize_raw_fixture(
            fixture_record.payload,
            clock=self.clock,
            fixture_path=str(request.fixture_path),
        )
        storage_locations: list[ArtifactStorageLocation] = []
        artifact_root = request.output_root
        if artifact_root is None:
            artifact_root = get_settings().resolved_artifact_root / "ingestion"
        store = LocalArtifactStore(root=artifact_root, clock=self.clock)
        if request.persist_raw:
            storage_locations.append(
                store.persist_raw_fixture(
                    source_reference_id=normalized.source_reference.source_reference_id,
                    fixture_type=normalized.fixture_type,
                    raw_text=fixture_record.raw_text,
                )
            )
        if request.persist_normalized:
            storage_locations.extend(self._persist_normalized_artifacts(store=store, normalized=normalized))

        return FixtureIngestionResponse(
            ingestion_job_id=make_prefixed_id("ingest"),
            fixture_name=normalized.fixture_name,
            fixture_type=normalized.fixture_type,
            ingested_at=normalized.ingested_at,
            source_reference=normalized.source_reference,
            company=normalized.company,
            filing=normalized.filing,
            earnings_call=normalized.earnings_call,
            news_item=normalized.news_item,
            price_series_metadata=normalized.price_series_metadata,
            storage_locations=storage_locations,
        )

    def _persist_normalized_artifacts(
        self,
        *,
        store: LocalArtifactStore,
        normalized: FixtureNormalizationResult,
    ) -> list[ArtifactStorageLocation]:
        """Persist normalized artifacts emitted by fixture normalization."""

        storage_locations = [
            store.persist_normalized_model(
                artifact_id=normalized.source_reference.source_reference_id,
                category="source_references",
                model=normalized.source_reference,
                source_reference_ids=[normalized.source_reference.source_reference_id],
            )
        ]
        if normalized.company is not None:
            storage_locations.append(
                store.persist_normalized_model(
                    artifact_id=normalized.company.company_id,
                    category="companies",
                    model=normalized.company,
                    source_reference_ids=[normalized.source_reference.source_reference_id],
                )
            )
        document_artifact = self._document_artifact(normalized)
        if document_artifact is not None:
            category, model = document_artifact
            storage_locations.append(
                store.persist_normalized_model(
                    artifact_id=model.document_id,
                    category=category,
                    model=model,
                    source_reference_ids=[normalized.source_reference.source_reference_id],
                )
            )
        if normalized.price_series_metadata is not None:
            storage_locations.append(
                store.persist_normalized_model(
                    artifact_id=normalized.price_series_metadata.price_series_metadata_id,
                    category="price_series_metadata",
                    model=normalized.price_series_metadata,
                    source_reference_ids=[normalized.source_reference.source_reference_id],
                )
            )
        return storage_locations

    def _document_artifact(
        self,
        normalized: FixtureNormalizationResult,
    ) -> tuple[str, Filing | EarningsCall | NewsItem] | None:
        """Return the normalized document artifact, if one exists."""

        if normalized.filing is not None:
            return "filings", normalized.filing
        if normalized.earnings_call is not None:
            return "earnings_calls", normalized.earnings_call
        if normalized.news_item is not None:
            return "news_items", normalized.news_item
        return None
