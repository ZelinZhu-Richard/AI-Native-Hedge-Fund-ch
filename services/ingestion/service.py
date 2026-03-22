from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field, model_validator

from libraries.config import get_settings
from libraries.core import resolve_artifact_workspace, resolve_artifact_workspace_from_stage_root
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    DocumentKind,
    EarningsCall,
    Filing,
    NewsItem,
    PipelineEventType,
    StrictModel,
    WorkflowStatus,
)
from libraries.utils import make_prefixed_id
from services.entity_resolution import (
    EntityResolutionService,
    ResolveEntityWorkspaceRequest,
)
from services.ingestion.fixture_loader import load_fixture_record
from services.ingestion.normalization import FixtureNormalizationResult, normalize_raw_fixture
from services.ingestion.storage import LocalArtifactStore
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.timing import TimingService


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

        artifact_root = request.output_root
        workspace = (
            resolve_artifact_workspace_from_stage_root(artifact_root)
            if artifact_root is not None
            else resolve_artifact_workspace(workspace_root=get_settings().resolved_artifact_root)
        )
        if artifact_root is None:
            artifact_root = workspace.ingestion_root
        monitoring_root = workspace.monitoring_root
        timing_root = workspace.timing_root
        monitoring_service = MonitoringService(clock=self.clock)
        ingestion_job_id = make_prefixed_id("ingest")
        started_at = self.clock.now()
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="fixture_ingestion",
                workflow_run_id=ingestion_job_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message=f"Fixture ingestion started for `{request.fixture_path.name}`.",
                related_artifact_ids=[str(request.fixture_path)],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        try:
            fixture_record = load_fixture_record(request.fixture_path)
            normalized = normalize_raw_fixture(
                fixture_record.payload,
                clock=self.clock,
                fixture_path=str(request.fixture_path),
            )
            storage_locations: list[ArtifactStorageLocation] = []
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
                storage_locations.extend(
                    self._persist_normalized_artifacts(store=store, normalized=normalized)
                )
                if normalized.timing_anomalies:
                    timing_response = TimingService(clock=self.clock).persist_anomalies(
                        anomalies=normalized.timing_anomalies,
                        output_root=timing_root,
                    )
                    storage_locations.extend(timing_response.storage_locations)
                entity_resolution_response = EntityResolutionService(
                    clock=self.clock
                ).resolve_entity_workspace(
                    ResolveEntityWorkspaceRequest(
                        ingestion_root=artifact_root,
                        parsing_root=None,
                        company_id=normalized.company.company_id if normalized.company is not None else None,
                        document_ids=(
                            [document_artifact[1].document_id]
                            if (document_artifact := self._document_artifact(normalized)) is not None
                            else []
                        ),
                        output_root=workspace.entity_resolution_root,
                        requested_by=request.requested_by,
                    )
                )
                storage_locations.extend(entity_resolution_response.storage_locations)

            response = FixtureIngestionResponse(
                ingestion_job_id=ingestion_job_id,
                fixture_name=normalized.fixture_name,
                fixture_type=normalized.fixture_type,
                ingested_at=normalized.ingested_at,
                source_reference=normalized.source_reference,
                source_availability_window=normalized.source_availability_window,
                company=normalized.company,
                filing=normalized.filing,
                earnings_call=normalized.earnings_call,
                news_item=normalized.news_item,
                price_series_metadata=normalized.price_series_metadata,
                timing_anomalies=normalized.timing_anomalies,
                storage_locations=storage_locations,
            )
            completed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="fixture_ingestion",
                    workflow_run_id=ingestion_job_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_COMPLETED,
                    status=WorkflowStatus.SUCCEEDED,
                    message=(
                        f"Fixture ingestion completed for `{request.fixture_path.name}` "
                        f"with {len(storage_locations)} persisted artifacts."
                    ),
                    related_artifact_ids=[
                        response.source_reference.source_reference_id,
                        *[location.artifact_id for location in storage_locations],
                    ],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="fixture_ingestion",
                    workflow_run_id=ingestion_job_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.SUCCEEDED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=storage_locations,
                    produced_artifact_ids=[
                        response.source_reference.source_reference_id,
                        *( [response.company.company_id] if response.company is not None else [] ),
                        *( [response.filing.document_id] if response.filing is not None else [] ),
                        *(
                            [response.earnings_call.document_id]
                            if response.earnings_call is not None
                            else []
                        ),
                        *( [response.news_item.document_id] if response.news_item is not None else [] ),
                        *(
                            [response.price_series_metadata.price_series_metadata_id]
                            if response.price_series_metadata is not None
                            else []
                        ),
                        *[location.artifact_id for location in storage_locations],
                    ],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        completed_event.pipeline_event.pipeline_event_id,
                    ],
                    notes=[
                        f"fixture_path={request.fixture_path}",
                        f"persist_raw={request.persist_raw}",
                        f"persist_normalized={request.persist_normalized}",
                        f"timing_anomaly_count={len(response.timing_anomalies)}",
                    ],
                    outputs_expected=request.persist_raw or request.persist_normalized,
                ),
                output_root=monitoring_root,
            )
            return response
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="fixture_ingestion",
                    workflow_run_id=ingestion_job_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=f"Fixture ingestion failed for `{request.fixture_path.name}`: {exc}",
                    related_artifact_ids=[str(request.fixture_path)],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="fixture_ingestion",
                    workflow_run_id=ingestion_job_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=[],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=[f"fixture_path={request.fixture_path}"],
                    outputs_expected=request.persist_raw or request.persist_normalized,
                ),
                output_root=monitoring_root,
            )
            raise

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
