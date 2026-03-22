from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import resolve_artifact_workspace, resolve_artifact_workspace_from_stage_root
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    DataLayer,
    DocumentEvidenceBundle,
    PipelineEventType,
    QualityDecision,
    RefusalReason,
    StrictModel,
    ValidationGate,
    WorkflowStatus,
)
from libraries.utils import make_prefixed_id
from services.data_quality import DataQualityRefusalError, DataQualityService
from services.entity_resolution import (
    EntityResolutionService,
    ResolveEntityWorkspaceRequest,
)
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.parsing.extraction import build_document_evidence_bundle
from services.parsing.loaders import load_parsing_inputs
from services.parsing.segmentation import build_parsed_document_text, segment_document
from services.parsing.storage import LocalParsingArtifactStore
from services.timing import TimingService


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
    validation_gate: ValidationGate | None = Field(
        default=None,
        description="Data-quality gate recorded for parsing output when validation ran.",
    )
    quality_decision: QualityDecision | None = Field(
        default=None,
        description="Overall decision emitted by the parsing data-quality gate.",
    )
    refusal_reason: RefusalReason | None = Field(
        default=None,
        description="Primary refusal reason when parsing input or output was blocked.",
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
        started_at = self.clock.now()
        monitoring_notes = [
            f"document_path={request.document_path}",
            f"source_reference_path={request.source_reference_path}",
            f"raw_payload_path={request.raw_payload_path}",
        ]
        output_root = request.output_root
        workspace = (
            resolve_artifact_workspace_from_stage_root(output_root)
            if output_root is not None
            else resolve_artifact_workspace(workspace_root=get_settings().resolved_artifact_root)
        )
        if output_root is None:
            output_root = workspace.parsing_root
        monitoring_root = workspace.monitoring_root
        timing_root = workspace.timing_root
        quality_root = workspace.data_quality_root
        monitoring_service = MonitoringService(clock=self.clock)
        quality_service = DataQualityService(clock=self.clock)
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="evidence_extraction",
                workflow_run_id=extraction_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message=f"Evidence extraction started for `{request.document_path.name}`.",
                related_artifact_ids=[str(request.document_path)],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        storage_locations: list[ArtifactStorageLocation] = []
        try:
            inputs = load_parsing_inputs(
                document_path=request.document_path,
                source_reference_path=request.source_reference_path,
                raw_payload_path=request.raw_payload_path,
            )
            input_validation = quality_service.validate_parsing_inputs(
                document=inputs.document,
                source_reference=inputs.source_reference,
                workflow_run_id=extraction_run_id,
                requested_by=request.requested_by,
                output_root=quality_root,
            )
            storage_locations.extend(input_validation.storage_locations)
            parsed_document_text = build_parsed_document_text(
                inputs=inputs,
                clock=self.clock,
                workflow_run_id=extraction_run_id,
                notes=monitoring_notes,
            )
            segments = segment_document(
                parsed_document_text=parsed_document_text,
                inputs=inputs,
                clock=self.clock,
                workflow_run_id=extraction_run_id,
                notes=monitoring_notes,
            )
            bundle = build_document_evidence_bundle(
                parsed_document_text=parsed_document_text,
                segments=segments,
                inputs=inputs,
                clock=self.clock,
                workflow_run_id=extraction_run_id,
                notes=monitoring_notes,
            )
            timing_service = TimingService(clock=self.clock)
            publication_timing, availability_window, timing_anomalies = (
                timing_service.build_document_timing(
                    document=inputs.document,
                    source_reference=inputs.source_reference,
                )
            )
            bundle = bundle.model_copy(
                update={
                    "publication_timing": publication_timing,
                    "availability_window": availability_window,
                    "timing_anomalies": timing_anomalies,
                }
            )
            output_validation = quality_service.validate_evidence_bundle(
                bundle=bundle,
                workflow_run_id=extraction_run_id,
                requested_by=request.requested_by,
                output_root=quality_root,
            )
            storage_locations.extend(output_validation.storage_locations)

            store = LocalParsingArtifactStore(root=output_root, clock=self.clock)
            storage_locations.extend(self._persist_bundle(store=store, bundle=bundle))
            if bundle.timing_anomalies:
                timing_response = timing_service.persist_anomalies(
                    anomalies=bundle.timing_anomalies,
                    output_root=timing_root,
                )
                storage_locations.extend(timing_response.storage_locations)
            entity_resolution_response = EntityResolutionService(clock=self.clock).resolve_entity_workspace(
                ResolveEntityWorkspaceRequest(
                    ingestion_root=_resolve_ingestion_root_from_source_reference_path(
                        request.source_reference_path
                    ),
                    parsing_root=output_root,
                    company_id=bundle.company_id,
                    document_ids=[bundle.document_id],
                    output_root=workspace.entity_resolution_root,
                    requested_by=request.requested_by,
                )
            )
            storage_locations.extend(entity_resolution_response.storage_locations)
            response = ExtractDocumentEvidenceResponse(
                extraction_run_id=extraction_run_id,
                storage_locations=storage_locations,
                document_id=bundle.document_id,
                source_reference_id=bundle.source_reference_id,
                company_id=bundle.company_id,
                publication_timing=bundle.publication_timing,
                availability_window=bundle.availability_window,
                document_kind=bundle.document_kind,
                parsed_document_text=bundle.parsed_document_text,
                segments=bundle.segments,
                evidence_spans=bundle.evidence_spans,
                claims=bundle.claims,
                risk_factors=bundle.risk_factors,
                guidance_changes=bundle.guidance_changes,
                tone_markers=bundle.tone_markers,
                evaluation=bundle.evaluation,
                timing_anomalies=bundle.timing_anomalies,
                validation_gate=output_validation.validation_gate,
                quality_decision=output_validation.validation_gate.decision,
                refusal_reason=output_validation.validation_gate.refusal_reason,
            )
            completed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="evidence_extraction",
                    workflow_run_id=extraction_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_COMPLETED,
                    status=WorkflowStatus.SUCCEEDED,
                    message=(
                        f"Evidence extraction completed for `{request.document_path.name}` "
                        f"with {len(storage_locations)} persisted artifacts."
                    ),
                    related_artifact_ids=[
                        response.document_id,
                        response.source_reference_id,
                        *[location.artifact_id for location in storage_locations],
                    ],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="evidence_extraction",
                    workflow_run_id=extraction_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.SUCCEEDED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=storage_locations,
                    produced_artifact_ids=[
                        response.document_id,
                        response.source_reference_id,
                        response.parsed_document_text.parsed_document_text_id,
                        *[segment.document_segment_id for segment in response.segments],
                        *[evidence_span.evidence_span_id for evidence_span in response.evidence_spans],
                        *[claim.extracted_claim_id for claim in response.claims],
                        *[risk_factor.risk_factor_id for risk_factor in response.risk_factors],
                        *[
                            guidance_change.guidance_change_id
                            for guidance_change in response.guidance_changes
                        ],
                        *[tone_marker.tone_marker_id for tone_marker in response.tone_markers],
                        *[location.artifact_id for location in storage_locations],
                    ],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        completed_event.pipeline_event.pipeline_event_id,
                    ],
                    notes=[
                        *monitoring_notes,
                        f"timing_anomaly_count={len(response.timing_anomalies)}",
                    ],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            return response
        except DataQualityRefusalError as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="evidence_extraction",
                    workflow_run_id=extraction_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=(
                        f"Evidence extraction failed quality validation for "
                        f"`{request.document_path.name}`: {exc}"
                    ),
                    related_artifact_ids=[
                        str(request.document_path),
                        exc.result.validation_gate.validation_gate_id,
                        *[
                            location.artifact_id
                            for location in [*storage_locations, *exc.storage_locations]
                        ],
                    ],
                    notes=[
                        f"requested_by={request.requested_by}",
                        f"quality_decision={exc.result.validation_gate.decision.value}",
                        (
                            "refusal_reason="
                            f"{exc.result.validation_gate.refusal_reason.value}"
                            if exc.result.validation_gate.refusal_reason is not None
                            else "refusal_reason=none"
                        ),
                    ],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="evidence_extraction",
                    workflow_run_id=extraction_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=[*storage_locations, *exc.storage_locations],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=[
                        *monitoring_notes,
                        f"validation_gate_id={exc.result.validation_gate.validation_gate_id}",
                        f"quality_decision={exc.result.validation_gate.decision.value}",
                        (
                            "refusal_reason="
                            f"{exc.result.validation_gate.refusal_reason.value}"
                            if exc.result.validation_gate.refusal_reason is not None
                            else "refusal_reason=none"
                        ),
                    ],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="evidence_extraction",
                    workflow_run_id=extraction_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=(
                        f"Evidence extraction failed for `{request.document_path.name}`: {exc}"
                    ),
                    related_artifact_ids=[str(request.document_path)],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="evidence_extraction",
                    workflow_run_id=extraction_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=storage_locations,
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=monitoring_notes,
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise

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


def _resolve_ingestion_root_from_source_reference_path(source_reference_path: Path) -> Path:
    """Infer the ingestion root from a normalized source-reference path."""

    return source_reference_path.parents[2]
