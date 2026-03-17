from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from libraries.core import build_provenance
from libraries.schemas import ArtifactStorageLocation, DataLayer, StorageKind, StrictModel
from libraries.time import Clock


class LocalSignalArtifactStore:
    """Persist Day 5 signal artifacts to a local filesystem root."""

    def __init__(self, *, root: Path, clock: Clock) -> None:
        self.root = root
        self.clock = clock

    def persist_model(
        self,
        *,
        artifact_id: str,
        category: str,
        model: StrictModel,
        source_reference_ids: list[str],
    ) -> ArtifactStorageLocation:
        """Persist a signal artifact and return canonical storage metadata."""

        destination = self.root / category / f"{artifact_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        serialized = model.model_dump_json(indent=2)
        destination.write_text(serialized, encoding="utf-8")
        content_hash = sha256(serialized.encode("utf-8")).hexdigest()
        now = self.clock.now()
        return ArtifactStorageLocation(
            artifact_storage_location_id=f"store_{content_hash[:24]}",
            artifact_id=artifact_id,
            storage_kind=StorageKind.LOCAL_FILESYSTEM,
            data_layer=DataLayer.DERIVED,
            uri=destination.resolve().as_uri(),
            content_hash=content_hash,
            retention_policy="local_development",
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="local_signal_artifact_store",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[artifact_id],
            ),
            created_at=now,
            updated_at=now,
        )
