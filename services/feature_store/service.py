from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import resolve_artifact_workspace, resolve_artifact_workspace_from_stage_root
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AblationView,
    ArtifactStorageLocation,
    AuditOutcome,
    Feature,
    FeatureDefinition,
    FeatureValue,
    PipelineEventType,
    QualityDecision,
    RefusalReason,
    StrictModel,
    TimingAnomaly,
    ValidationGate,
    WorkflowStatus,
)
from libraries.utils import make_canonical_id, make_prefixed_id
from services.audit import AuditEventRequest, AuditLoggingService
from services.data_quality import DataQualityRefusalError, DataQualityService
from services.feature_store.loaders import load_feature_mapping_inputs
from services.feature_store.mapping import build_feature_candidates
from services.feature_store.storage import LocalFeatureArtifactStore
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.timing import TimingService


class FeatureWriteRequest(StrictModel):
    """Request to store point-in-time feature values."""

    features: list[Feature] = Field(description="Feature values to upsert.")
    requested_by: str = Field(description="Requester identifier.")


class FeatureWriteResponse(StrictModel):
    """Response returned after writing features."""

    write_batch_id: str = Field(description="Identifier for the feature write batch.")
    accepted_feature_ids: list[str] = Field(
        default_factory=list,
        description="Feature identifiers accepted for storage.",
    )
    accepted_at: datetime = Field(description="UTC timestamp when the write was accepted.")


class FeatureQueryRequest(StrictModel):
    """Request to fetch point-in-time features."""

    entity_id: str = Field(description="Entity to query.")
    as_of_time: datetime = Field(
        description="Maximum information time allowed for feature retrieval."
    )
    feature_names: list[str] = Field(
        default_factory=list, description="Subset of features requested."
    )


class FeatureQueryResponse(StrictModel):
    """Response containing point-in-time feature values."""

    snapshot_id: str | None = Field(default=None, description="Snapshot used to satisfy the query.")
    features: list[Feature] = Field(default_factory=list, description="Returned feature values.")


class RunFeatureMappingRequest(StrictModel):
    """Explicit local request to build Day 5 candidate features from research artifacts."""

    research_root: Path = Field(description="Root path for persisted research artifacts.")
    parsing_root: Path | None = Field(
        default=None,
        description="Optional parsing artifact root used to reload guidance, risk, and tone artifacts.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional feature artifact root. Defaults to the configured artifact root.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when the research root contains multiple companies.",
    )
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional research cutoff. When omitted, latest-artifact loading is used for local development only.",
    )
    ablation_view: AblationView = Field(
        default=AblationView.TEXT_ONLY,
        description="Requested ablation slice for feature generation.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunFeatureMappingResponse(StrictModel):
    """Result of a local Day 5 feature-mapping workflow."""

    feature_mapping_run_id: str = Field(description="Canonical workflow identifier.")
    company_id: str = Field(description="Covered company identifier.")
    feature_definitions: list[FeatureDefinition] = Field(
        default_factory=list,
        description="Feature definitions materialized during the workflow.",
    )
    feature_values: list[FeatureValue] = Field(
        default_factory=list,
        description="Feature values materialized during the workflow.",
    )
    features: list[Feature] = Field(
        default_factory=list,
        description="Primary candidate feature artifacts materialized during the workflow.",
    )
    timing_anomalies: list[TimingAnomaly] = Field(
        default_factory=list,
        description="Structured timing anomalies observed during feature availability resolution.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work, assumptions, or gaps.",
    )
    validation_gate: ValidationGate | None = Field(
        default=None,
        description="Data-quality gate recorded for feature mapping when validation ran.",
    )
    quality_decision: QualityDecision | None = Field(
        default=None,
        description="Overall decision emitted by the feature-mapping validation gate.",
    )
    refusal_reason: RefusalReason | None = Field(
        default=None,
        description="Primary refusal reason when feature mapping was blocked.",
    )


class FeatureStoreService(BaseService):
    """Store, retrieve, and locally materialize point-in-time candidate features."""

    capability_name = "feature_store"
    capability_description = "Stores point-in-time features and materializes candidate features from reviewed research."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["ResearchBrief", "Hypothesis", "CounterHypothesis", "EvidenceAssessment"],
            produces=["FeatureDefinition", "FeatureValue", "Feature", "DataSnapshot"],
            api_routes=[],
        )

    def write_features(self, request: FeatureWriteRequest) -> FeatureWriteResponse:
        """Persist feature artifacts to the local Day 5 artifact root."""

        workspace = resolve_artifact_workspace()
        store = LocalFeatureArtifactStore(
            root=workspace.signal_root,
            clock=self.clock,
        )
        for feature in request.features:
            self._persist_feature(store=store, feature=feature)
        return FeatureWriteResponse(
            write_batch_id=make_prefixed_id("featurebatch"),
            accepted_feature_ids=[feature.feature_id for feature in request.features],
            accepted_at=self.clock.now(),
        )

    def query_features(self, request: FeatureQueryRequest) -> FeatureQueryResponse:
        """Read persisted local candidate features subject to a point-in-time cutoff."""

        feature_root = resolve_artifact_workspace().signal_root / "features"
        features = _load_features(feature_root)
        filtered = [
            feature
            for feature in features
            if feature.entity_id == request.entity_id
            and feature.feature_value.available_at <= request.as_of_time
            and (
                not request.feature_names
                or feature.feature_definition.name in set(request.feature_names)
            )
        ]
        filtered.sort(
            key=lambda feature: (
                feature.feature_value.available_at,
                feature.feature_definition.name,
            )
        )
        snapshot_id = (
            make_canonical_id("snap", request.entity_id, request.as_of_time.isoformat())
            if filtered
            else None
        )
        return FeatureQueryResponse(snapshot_id=snapshot_id, features=filtered)

    def run_feature_mapping_workflow(
        self,
        request: RunFeatureMappingRequest,
    ) -> RunFeatureMappingResponse:
        """Execute deterministic Day 5 feature mapping from research artifacts."""

        feature_mapping_run_id = make_prefixed_id("fmap")
        output_root = request.output_root or (
            get_settings().resolved_artifact_root / "signal_generation"
        )
        output_workspace = resolve_artifact_workspace_from_stage_root(output_root)
        research_workspace = resolve_artifact_workspace_from_stage_root(request.research_root)
        audit_root = output_workspace.audit_root
        monitoring_root = output_workspace.monitoring_root
        timing_root = output_workspace.timing_root
        quality_root = output_workspace.data_quality_root
        monitoring_service = MonitoringService(clock=self.clock)
        quality_service = DataQualityService(clock=self.clock)
        started_at = self.clock.now()
        storage_locations: list[ArtifactStorageLocation] = []
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="feature_mapping",
                workflow_run_id=feature_mapping_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message="Feature mapping workflow started.",
                related_artifact_ids=[],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        inferred_parsing_root = request.parsing_root
        if inferred_parsing_root is None:
            sibling_parsing_root = research_workspace.parsing_root
            inferred_parsing_root = sibling_parsing_root if sibling_parsing_root.exists() else None

        try:
            inputs = load_feature_mapping_inputs(
                research_root=request.research_root,
                parsing_root=inferred_parsing_root,
                ingestion_root=(
                    research_workspace.ingestion_root
                    if research_workspace.ingestion_root.exists()
                    else None
                ),
                company_id=request.company_id,
                as_of_time=request.as_of_time,
            )
            input_validation = quality_service.validate_feature_mapping_inputs(
                inputs=inputs,
                workflow_run_id=feature_mapping_run_id,
                requested_by=request.requested_by,
                output_root=quality_root,
            )
            result = build_feature_candidates(
                inputs=inputs,
                ablation_view=request.ablation_view,
                clock=self.clock,
                workflow_run_id=feature_mapping_run_id,
            )
            output_validation = quality_service.validate_feature_output(
                company_id=inputs.company_id,
                features=result.features,
                workflow_run_id=feature_mapping_run_id,
                requested_by=request.requested_by,
                output_root=quality_root,
            )
            store = LocalFeatureArtifactStore(root=output_root, clock=self.clock)
            storage_locations = [
                *input_validation.storage_locations,
                *output_validation.storage_locations,
            ]
            for feature_definition in result.feature_definitions:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=feature_definition.feature_definition_id,
                        category="feature_definitions",
                        model=feature_definition,
                        source_reference_ids=feature_definition.provenance.source_reference_ids,
                    )
                )
            for feature_value in result.feature_values:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=feature_value.feature_value_id,
                        category="feature_values",
                        model=feature_value,
                        source_reference_ids=feature_value.provenance.source_reference_ids,
                    )
                )
            for feature in result.features:
                storage_locations.append(self._persist_feature(store=store, feature=feature))
            if result.timing_anomalies:
                timing_response = TimingService(clock=self.clock).persist_anomalies(
                    anomalies=result.timing_anomalies,
                    output_root=timing_root,
                )
                storage_locations.extend(timing_response.storage_locations)
            notes = list(result.notes)
            if request.as_of_time is None:
                notes.append(
                    "No as_of_time provided; latest-artifact loading is a local-development convenience and not replay-safe."
                )
            else:
                notes.append(f"as_of_time={request.as_of_time.isoformat()}")
            audit_response = AuditLoggingService(clock=self.clock).record_event(
                AuditEventRequest(
                    event_type=(
                        "feature_mapping_completed"
                        if result.features
                        else "feature_mapping_blocked"
                    ),
                    actor_type="service",
                    actor_id="feature_store",
                    target_type="feature_mapping_workflow",
                    target_id=feature_mapping_run_id,
                    action="completed" if result.features else "blocked",
                    outcome=AuditOutcome.SUCCESS if result.features else AuditOutcome.WARNING,
                    reason=(
                        "Candidate features were materialized from research artifacts."
                        if result.features
                        else "No candidate features were materialized for the requested research slice."
                    ),
                    request_id=feature_mapping_run_id,
                    related_artifact_ids=[
                        *[
                            feature_definition.feature_definition_id
                            for feature_definition in result.feature_definitions
                        ],
                        *[feature_value.feature_value_id for feature_value in result.feature_values],
                        *[feature.feature_id for feature in result.features],
                        *[anomaly.timing_anomaly_id for anomaly in result.timing_anomalies],
                    ],
                    notes=notes,
                ),
                output_root=audit_root,
            )
            storage_locations.append(audit_response.storage_location)
            completed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="feature_mapping",
                    workflow_run_id=feature_mapping_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_COMPLETED,
                    status=WorkflowStatus.SUCCEEDED,
                    message=(
                        "Feature mapping workflow completed."
                        if result.features
                        else "Feature mapping workflow completed without materialized features."
                    ),
                    related_artifact_ids=[
                        *[
                            feature_definition.feature_definition_id
                            for feature_definition in result.feature_definitions
                        ],
                        *[feature_value.feature_value_id for feature_value in result.feature_values],
                        *[feature.feature_id for feature in result.features],
                    ],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            pipeline_event_ids = [
                start_event.pipeline_event.pipeline_event_id,
                completed_event.pipeline_event.pipeline_event_id,
            ]
            summary_status = WorkflowStatus.SUCCEEDED
            attention_reasons: list[str] = []
            if not result.features:
                attention_event = monitoring_service.record_pipeline_event(
                    RecordPipelineEventRequest(
                        workflow_name="feature_mapping",
                        workflow_run_id=feature_mapping_run_id,
                        service_name=self.capability_name,
                        event_type=PipelineEventType.ATTENTION_REQUIRED,
                        status=WorkflowStatus.ATTENTION_REQUIRED,
                        message="Feature mapping produced no candidate features.",
                        related_artifact_ids=[],
                        notes=[f"requested_by={request.requested_by}"],
                    ),
                    output_root=monitoring_root,
                )
                pipeline_event_ids.append(attention_event.pipeline_event.pipeline_event_id)
                summary_status = WorkflowStatus.ATTENTION_REQUIRED
                attention_reasons.append("no_candidate_features")
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="feature_mapping",
                    workflow_run_id=feature_mapping_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=summary_status,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=storage_locations,
                    produced_artifact_ids=[
                        *[
                            feature_definition.feature_definition_id
                            for feature_definition in result.feature_definitions
                        ],
                        *[feature_value.feature_value_id for feature_value in result.feature_values],
                        *[feature.feature_id for feature in result.features],
                    ],
                    pipeline_event_ids=pipeline_event_ids,
                    attention_reasons=attention_reasons,
                    notes=notes,
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            return RunFeatureMappingResponse(
                feature_mapping_run_id=feature_mapping_run_id,
                company_id=inputs.company_id,
                feature_definitions=result.feature_definitions,
                feature_values=result.feature_values,
                features=result.features,
                timing_anomalies=result.timing_anomalies,
                storage_locations=storage_locations,
                notes=notes,
                validation_gate=output_validation.validation_gate,
                quality_decision=output_validation.validation_gate.decision,
                refusal_reason=output_validation.validation_gate.refusal_reason,
            )
        except DataQualityRefusalError as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="feature_mapping",
                    workflow_run_id=feature_mapping_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=f"Feature mapping workflow failed quality validation: {exc}",
                    related_artifact_ids=[exc.result.validation_gate.validation_gate_id],
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
                    workflow_name="feature_mapping",
                    workflow_run_id=feature_mapping_run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=exc.storage_locations,
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=[
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
                    workflow_name="feature_mapping",
                    workflow_run_id=feature_mapping_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=f"Feature mapping workflow failed: {exc}",
                    related_artifact_ids=[],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="feature_mapping",
                    workflow_run_id=feature_mapping_run_id,
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
                    notes=[f"requested_by={request.requested_by}"],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise

    def _persist_feature(
        self,
        *,
        store: LocalFeatureArtifactStore,
        feature: Feature,
    ) -> ArtifactStorageLocation:
        """Persist one feature artifact."""

        return store.persist_model(
            artifact_id=feature.feature_id,
            category="features",
            model=feature,
            source_reference_ids=feature.provenance.source_reference_ids,
        )


def _load_features(directory: Path) -> list[Feature]:
    """Load persisted local candidate features."""

    if not directory.exists():
        return []
    return [
        Feature.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
