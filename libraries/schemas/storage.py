from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

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


class DatasetPartition(TimestampedModel):
    """Logical partition metadata for a reproducible dataset slice."""

    dataset_partition_id: str = Field(description="Canonical dataset partition identifier.")
    dataset_name: str = Field(description="Canonical dataset name.")
    partition_key: str = Field(
        description="Logical partition key, such as company or publish date."
    )
    partition_value: str = Field(description="Logical partition value.")
    date_range_start: date | None = Field(
        default=None, description="Optional partition start date."
    )
    date_range_end: date | None = Field(default=None, description="Optional partition end date.")
    storage_location_id: str | None = Field(
        default=None,
        description="Backing storage location identifier when materialized.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the partition record.")


class DatasetManifest(TimestampedModel):
    """Manifest describing a versioned, reproducible dataset available to workflows."""

    dataset_manifest_id: str = Field(description="Canonical dataset manifest identifier.")
    dataset_name: str = Field(description="Canonical dataset name.")
    dataset_version: str = Field(description="Version label for the dataset manifest.")
    schema_version: str = Field(description="Schema version for the dataset.")
    data_layer: DataLayer = Field(description="Primary layer represented by the dataset.")
    partition_ids: list[str] = Field(
        default_factory=list,
        description="Partition identifiers that compose the manifest.",
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
