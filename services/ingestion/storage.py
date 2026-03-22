from __future__ import annotations

from pathlib import Path

from libraries.core import persist_local_model, persist_local_text
from libraries.schemas import ArtifactStorageLocation, DataLayer, StrictModel
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

        return persist_local_text(
            root=self.root,
            relative_path=Path("raw") / fixture_type / f"{source_reference_id}.json",
            artifact_id=source_reference_id,
            raw_text=raw_text,
            data_layer=DataLayer.RAW,
            source_reference_ids=[source_reference_id],
            clock=self.clock,
            transformation_name="local_artifact_store",
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

        return persist_local_model(
            root=self.root / "normalized",
            category=category,
            artifact_id=artifact_id,
            model=model,
            source_reference_ids=source_reference_ids,
            data_layer=DataLayer.NORMALIZED,
            clock=self.clock,
            transformation_name="local_artifact_store",
        )
