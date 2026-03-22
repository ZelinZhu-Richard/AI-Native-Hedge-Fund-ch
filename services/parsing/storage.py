from __future__ import annotations

from pathlib import Path

from libraries.core import persist_local_model
from libraries.schemas import ArtifactStorageLocation, DataLayer, StrictModel
from libraries.time import Clock


class LocalParsingArtifactStore:
    """Persist parser-owned artifacts to a local filesystem root."""

    def __init__(self, *, root: Path, clock: Clock) -> None:
        self.root = root
        self.clock = clock

    def persist_model(
        self,
        *,
        artifact_id: str,
        category: str,
        model: StrictModel,
        data_layer: DataLayer,
        source_reference_ids: list[str],
    ) -> ArtifactStorageLocation:
        """Persist a parsing artifact and return its storage metadata."""

        return persist_local_model(
            root=self.root,
            category=category,
            artifact_id=artifact_id,
            model=model,
            source_reference_ids=source_reference_ids,
            data_layer=data_layer,
            clock=self.clock,
            transformation_name="local_parsing_artifact_store",
        )
