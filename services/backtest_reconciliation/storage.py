from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from libraries.core import load_local_models, persist_local_model
from libraries.schemas import ArtifactStorageLocation, StrictModel
from libraries.time import Clock

TModel = TypeVar("TModel", bound=StrictModel)


class LocalBacktestReconciliationArtifactStore:
    """Persist backtest-reconciliation artifacts to the local filesystem."""

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
        """Persist one reconciliation artifact and return storage metadata."""

        return persist_local_model(
            root=self.root,
            category=category,
            artifact_id=artifact_id,
            model=model,
            source_reference_ids=source_reference_ids,
            clock=self.clock,
            transformation_name="local_backtest_reconciliation_artifact_store",
        )


def load_models(
    *,
    root: Path,
    category: str,
    model_cls: type[TModel],
) -> list[TModel]:
    """Load persisted reconciliation artifacts from one category when present."""

    return load_local_models(root / category, model_cls)
