from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import Feature, StrictModel
from libraries.utils import make_prefixed_id


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


class FeatureStoreService(BaseService):
    """Store and retrieve point-in-time features with temporal discipline."""

    capability_name = "feature_store"
    capability_description = "Stores point-in-time features and serves temporally valid reads."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Feature"],
            produces=["Feature", "DataSnapshot"],
            api_routes=[],
        )

    def write_features(self, request: FeatureWriteRequest) -> FeatureWriteResponse:
        """Accept a feature batch for storage."""

        return FeatureWriteResponse(
            write_batch_id=make_prefixed_id("featurebatch"),
            accepted_feature_ids=[feature.feature_id for feature in request.features],
            accepted_at=self.clock.now(),
        )

    def query_features(self, request: FeatureQueryRequest) -> FeatureQueryResponse:
        """Return an empty point-in-time feature response until storage exists."""

        return FeatureQueryResponse(snapshot_id=None, features=[])
