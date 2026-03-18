from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from libraries.schemas.base import DataLayer, ProvenanceRecord, TimestampedModel


class StorageKind(StrEnum):
    """Canonical storage classes for artifact and dataset metadata."""

    LOCAL_FILESYSTEM = "local_filesystem"
    OBJECT_STORE = "object_store"
    DATABASE = "database"
    DATA_WAREHOUSE = "data_warehouse"


class ArtifactStorageLocation(TimestampedModel):
    """Versioned metadata for where a materialized artifact lives."""

    artifact_storage_location_id: str = Field(description="Canonical storage location identifier.")
    artifact_id: str = Field(description="Artifact identifier stored at this location.")
    storage_kind: StorageKind = Field(description="Storage system class.")
    data_layer: DataLayer = Field(description="Data layer of the stored artifact.")
    uri: str = Field(description="Canonical retrieval URI.")
    content_hash: str | None = Field(
        default=None,
        description="Content hash for integrity or duplicate detection.",
    )
    retention_policy: str | None = Field(
        default=None,
        description="Retention policy label for the stored artifact.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the storage record.")


class DatasetUsageRole(StrEnum):
    """How a dataset is used by an experiment or workflow."""

    INPUT = "input"
    REFERENCE = "reference"
    BENCHMARK = "benchmark"


class SourceVersion(TimestampedModel):
    """Minimal source-family watermark record for reproducible dataset replay."""

    source_version_id: str = Field(description="Canonical source-version identifier.")
    source_family: str = Field(description="Canonical source-family label.")
    version_label: str = Field(description="Version or snapshot label for the source family.")
    storage_uri: str | None = Field(
        default=None,
        description="Storage URI or root associated with the source version.",
    )
    event_time_start: datetime | None = Field(
        default=None,
        description="Earliest event time represented by the source version when known.",
    )
    event_time_watermark: datetime | None = Field(
        default=None,
        description="Latest event time represented by the source version when known.",
    )
    ingestion_cutoff_time: datetime | None = Field(
        default=None,
        description="Latest ingestion cutoff represented by the source version when known.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Lineage or replay notes for the source version.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the source version.")

    @model_validator(mode="after")
    def validate_event_range(self) -> SourceVersion:
        """Ensure event-time ranges remain internally consistent."""

        if (
            self.event_time_start is not None
            and self.event_time_watermark is not None
            and self.event_time_watermark < self.event_time_start
        ):
            raise ValueError(
                "event_time_watermark must be greater than or equal to event_time_start."
            )
        return self


class DatasetPartition(TimestampedModel):
    """Logical partition metadata for a reproducible dataset slice."""

    dataset_partition_id: str = Field(description="Canonical dataset partition identifier.")
    dataset_name: str = Field(description="Canonical dataset name.")
    partition_key: str = Field(
        description="Logical partition key, such as company or publish date."
    )
    partition_value: str = Field(description="Logical partition value.")
    data_snapshot_id: str | None = Field(
        default=None,
        description="Snapshot identifier this partition belongs to when materialized.",
    )
    date_range_start: date | None = Field(
        default=None, description="Optional partition start date."
    )
    date_range_end: date | None = Field(default=None, description="Optional partition end date.")
    event_time_start: datetime | None = Field(
        default=None,
        description="Earliest event time in the partition when known.",
    )
    event_time_end: datetime | None = Field(
        default=None,
        description="Latest event time in the partition when known.",
    )
    ingestion_cutoff_time: datetime | None = Field(
        default=None,
        description="Latest ingestion cutoff represented by the partition when known.",
    )
    row_count: int | None = Field(
        default=None,
        ge=0,
        description="Approximate row count for the partition.",
    )
    source_version_ids: list[str] = Field(
        default_factory=list,
        description="Source-version identifiers represented by the partition.",
    )
    storage_location_id: str | None = Field(
        default=None,
        description="Backing storage location identifier when materialized.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the partition record.")

    @model_validator(mode="after")
    def validate_partition_ranges(self) -> DatasetPartition:
        """Require internally consistent date and event-time ranges."""

        if (
            self.date_range_start is not None
            and self.date_range_end is not None
            and self.date_range_end < self.date_range_start
        ):
            raise ValueError("date_range_end must be greater than or equal to date_range_start.")
        if (
            self.event_time_start is not None
            and self.event_time_end is not None
            and self.event_time_end < self.event_time_start
        ):
            raise ValueError("event_time_end must be greater than or equal to event_time_start.")
        return self


class DatasetManifest(TimestampedModel):
    """Manifest describing a versioned, reproducible dataset available to workflows."""

    dataset_manifest_id: str = Field(description="Canonical dataset manifest identifier.")
    dataset_name: str = Field(description="Canonical dataset name.")
    dataset_version: str = Field(description="Version label for the dataset manifest.")
    schema_version: str = Field(description="Schema version for the dataset.")
    data_layer: DataLayer = Field(description="Primary layer represented by the dataset.")
    storage_uri: str | None = Field(
        default=None,
        description="Storage URI or root associated with the dataset manifest.",
    )
    partition_ids: list[str] = Field(
        default_factory=list,
        description="Partition identifiers that compose the manifest.",
    )
    source_families: list[str] = Field(
        default_factory=list,
        description="Canonical source-family labels represented by the manifest.",
    )
    source_version_ids: list[str] = Field(
        default_factory=list,
        description="Source-version identifiers referenced by the manifest.",
    )
    source_count: int | None = Field(
        default=None, ge=0, description="Count of contributing sources."
    )
    row_count: int | None = Field(default=None, ge=0, description="Approximate row count.")
    lineage_notes: list[str] = Field(
        default_factory=list,
        description="Important lineage caveats or reproducibility notes.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the dataset manifest.")


class DatasetReference(TimestampedModel):
    """Reference linking an experiment to one manifest-backed dataset snapshot."""

    dataset_reference_id: str = Field(description="Canonical dataset-reference identifier.")
    dataset_name: str = Field(description="Canonical dataset name.")
    usage_role: DatasetUsageRole = Field(description="How the dataset is used by the run.")
    dataset_manifest_id: str = Field(description="Dataset-manifest identifier.")
    data_snapshot_id: str = Field(description="Snapshot identifier referenced by the run.")
    data_layer: DataLayer = Field(description="Primary data layer represented by the dataset.")
    information_cutoff_time: datetime | None = Field(
        default=None,
        description="Information cutoff the run was allowed to assume for the dataset.",
    )
    schema_version: str = Field(description="Schema version attached to the dataset reference.")
    storage_uri: str = Field(description="Storage URI or root for the referenced dataset.")
    provenance: ProvenanceRecord = Field(description="Traceability for the dataset reference.")

    @model_validator(mode="after")
    def validate_reference(self) -> DatasetReference:
        """Require a stable storage URI for every dataset reference."""

        if not self.storage_uri:
            raise ValueError("storage_uri must be non-empty.")
        return self
