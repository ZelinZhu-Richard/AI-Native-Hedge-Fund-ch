from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from libraries.core import build_provenance
from libraries.schemas import ArtifactStorageLocation, DataLayer, StorageKind, StrictModel
from libraries.time import Clock


class LocalArtifactStore:
    """Persist raw and normalized ingestion artifacts to a local filesystem root."""

    def __init__(self, *, root: Path, clock: Clock) -> None:
        self.root = root
        self.clock = clock

    def persist_raw_fixture(
        self,
        *,
        source_reference_id: str,
        fixture_type: str,
        raw_text: str,
    ) -> ArtifactStorageLocation:
        """Persist a raw fixture payload under the raw storage layer."""

        return self._persist_text(
            artifact_id=source_reference_id,
            raw_text=raw_text,
            relative_path=Path("raw") / fixture_type / f"{source_reference_id}.json",
            data_layer=DataLayer.RAW,
            source_reference_ids=[source_reference_id],
        )

    def persist_normalized_model(
        self,
        *,
        artifact_id: str,
        category: str,
        model: StrictModel,
        source_reference_ids: list[str],
    ) -> ArtifactStorageLocation:
        """Persist a normalized model under the normalized storage layer."""

        return self._persist_model(
            artifact_id=artifact_id,
            model=model,
            relative_path=Path("normalized") / category / f"{artifact_id}.json",
            data_layer=DataLayer.NORMALIZED,
            source_reference_ids=source_reference_ids,
        )

    def _persist_text(
        self,
        *,
        artifact_id: str,
        raw_text: str,
        relative_path: Path,
        data_layer: DataLayer,
        source_reference_ids: list[str],
    ) -> ArtifactStorageLocation:
        """Write an exact raw payload to disk and record its storage location."""

        destination = self.root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(raw_text, encoding="utf-8")
        content_hash = sha256(raw_text.encode("utf-8")).hexdigest()
        return self._build_storage_location(
            artifact_id=artifact_id,
            destination=destination,
            data_layer=data_layer,
            content_hash=content_hash,
            source_reference_ids=source_reference_ids,
        )

    def _persist_model(
        self,
        *,
        artifact_id: str,
        model: StrictModel,
        relative_path: Path,
        data_layer: DataLayer,
        source_reference_ids: list[str],
    ) -> ArtifactStorageLocation:
        """Write a model to disk and return a canonical storage location record."""

        destination = self.root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        serialized = model.model_dump_json(indent=2)
        destination.write_text(serialized, encoding="utf-8")
        content_hash = sha256(serialized.encode("utf-8")).hexdigest()
        return self._build_storage_location(
            artifact_id=artifact_id,
            destination=destination,
            data_layer=data_layer,
            content_hash=content_hash,
            source_reference_ids=source_reference_ids,
        )

    def _build_storage_location(
        self,
        *,
        artifact_id: str,
        destination: Path,
        data_layer: DataLayer,
        content_hash: str,
        source_reference_ids: list[str],
    ) -> ArtifactStorageLocation:
        """Build a canonical storage record for a persisted artifact."""

        now = self.clock.now()
        return ArtifactStorageLocation(
            artifact_storage_location_id=f"store_{content_hash[:24]}",
            artifact_id=artifact_id,
            storage_kind=StorageKind.LOCAL_FILESYSTEM,
            data_layer=data_layer,
            uri=destination.resolve().as_uri(),
            content_hash=content_hash,
            retention_policy="local_development",
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="local_artifact_store",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[artifact_id],
            ),
            created_at=now,
            updated_at=now,
        )
