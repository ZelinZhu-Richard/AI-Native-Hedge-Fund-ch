from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AblationView,
    ArtifactStorageLocation,
    Feature,
    FeatureDefinition,
    FeatureValue,
    StrictModel,
)
from libraries.utils import make_canonical_id, make_prefixed_id
from services.feature_store.loaders import load_feature_mapping_inputs
from services.feature_store.mapping import build_feature_candidates
from services.feature_store.storage import LocalFeatureArtifactStore


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
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work, assumptions, or gaps.",
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

        store = LocalFeatureArtifactStore(
            root=get_settings().resolved_artifact_root / "signal_generation",
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

        feature_root = get_settings().resolved_artifact_root / "signal_generation" / "features"
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
        inferred_parsing_root = request.parsing_root
        if inferred_parsing_root is None:
            sibling_parsing_root = request.research_root.parent / "parsing"
            inferred_parsing_root = sibling_parsing_root if sibling_parsing_root.exists() else None

        inputs = load_feature_mapping_inputs(
            research_root=request.research_root,
            parsing_root=inferred_parsing_root,
            company_id=request.company_id,
        )
        result = build_feature_candidates(
            inputs=inputs,
            ablation_view=request.ablation_view,
            clock=self.clock,
            workflow_run_id=feature_mapping_run_id,
        )
        output_root = request.output_root or (
            get_settings().resolved_artifact_root / "signal_generation"
        )
        store = LocalFeatureArtifactStore(root=output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
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
        return RunFeatureMappingResponse(
            feature_mapping_run_id=feature_mapping_run_id,
            company_id=inputs.company_id,
            feature_definitions=result.feature_definitions,
            feature_values=result.feature_values,
            features=result.features,
            storage_locations=storage_locations,
            notes=result.notes,
        )

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
