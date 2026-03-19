from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import TypeVar

from libraries.core import build_provenance
from libraries.schemas import ArtifactStorageLocation, DataLayer, StorageKind, StrictModel
from libraries.time import Clock

TModel = TypeVar("TModel", bound=StrictModel)


class LocalRedTeamArtifactStore:
    """Persist red-team artifacts to the local filesystem."""

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
        """Persist one typed red-team artifact and return storage metadata."""

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
                transformation_name="local_red_team_artifact_store",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[artifact_id],
            ),
            created_at=now,
            updated_at=now,
        )


def load_models(
    *,
    root: Path,
    category: str,
    model_cls: type[TModel],
) -> list[TModel]:
    """Load persisted red-team-adjacent artifacts from one category when present."""

    directory = root / category
    if not directory.exists():
        return []
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
