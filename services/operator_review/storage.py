from __future__ import annotations

from pathlib import Path

from libraries.core import persist_local_model
from libraries.schemas import ArtifactStorageLocation, StrictModel
from libraries.time import Clock


class LocalReviewArtifactStore:
    """Persist Day 11 review artifacts to the local filesystem."""

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
        """Persist one typed review artifact and return storage metadata."""

        return persist_local_model(
            root=self.root,
            category=category,
            artifact_id=artifact_id,
            model=model,
            source_reference_ids=source_reference_ids,
            clock=self.clock,
            transformation_name="local_review_artifact_store",
        )
