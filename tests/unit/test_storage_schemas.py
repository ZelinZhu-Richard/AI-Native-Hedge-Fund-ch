from __future__ import annotations

from datetime import UTC, datetime

from libraries.schemas import ArtifactStorageLocation, DataLayer, DatasetManifest, StorageKind
from libraries.schemas.base import ProvenanceRecord


def test_dataset_manifest_and_storage_location_validate() -> None:
    now = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
    provenance = ProvenanceRecord(
        transformation_name="storage_schema_test",
        processing_time=now,
        config_version="day1",
    )

    manifest = DatasetManifest(
        dataset_manifest_id="manifest_test",
        dataset_name="documents",
        dataset_version="2026-03-16",
        schema_version="1.0.0",
        data_layer=DataLayer.NORMALIZED,
        partition_ids=["partition_test"],
        source_count=3,
        row_count=100,
        lineage_notes=["fixture manifest"],
        provenance=provenance,
        created_at=now,
        updated_at=now,
    )
    location = ArtifactStorageLocation(
        artifact_storage_location_id="store_test",
        artifact_id="doc_test",
        storage_kind=StorageKind.LOCAL_FILESYSTEM,
        data_layer=DataLayer.NORMALIZED,
        uri="file:///tmp/doc.txt",
        content_hash="abc123",
        provenance=provenance,
        created_at=now,
        updated_at=now,
    )

    assert manifest.dataset_name == "documents"
    assert location.storage_kind == StorageKind.LOCAL_FILESYSTEM
