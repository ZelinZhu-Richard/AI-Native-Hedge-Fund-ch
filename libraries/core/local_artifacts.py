from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Generic, TypeVar

from libraries.config import get_settings
from libraries.core.provenance import build_provenance
from libraries.schemas import ArtifactStorageLocation, DataLayer, StorageKind, StrictModel
from libraries.time import Clock

TModel = TypeVar("TModel", bound=StrictModel)


@dataclass(frozen=True)
class StoredLocalModel(Generic[TModel]):
    """One persisted model plus its filesystem location."""

    model: TModel
    path: Path

    @property
    def uri(self) -> str:
        """Return the canonical local file URI for the stored artifact."""

        return self.path.resolve().as_uri()


@dataclass(frozen=True)
class ArtifactWorkspace:
    """Standard local artifact layout used across current workflows."""

    root: Path
    ingestion_root: Path
    parsing_root: Path
    research_root: Path
    signal_root: Path
    signal_arbitration_root: Path
    backtesting_root: Path
    ablation_root: Path
    experiments_root: Path
    evaluation_root: Path
    portfolio_root: Path
    portfolio_analysis_root: Path
    review_root: Path
    audit_root: Path
    monitoring_root: Path
    timing_root: Path
    data_quality_root: Path
    reconciliation_root: Path
    entity_resolution_root: Path
    orchestration_root: Path
    red_team_root: Path


def resolve_artifact_workspace(*, workspace_root: Path | None = None) -> ArtifactWorkspace:
    """Resolve the standard local artifact layout for one workspace root."""

    resolved_root = (workspace_root or get_settings().resolved_artifact_root).resolve()
    return ArtifactWorkspace(
        root=resolved_root,
        ingestion_root=resolved_root / "ingestion",
        parsing_root=resolved_root / "parsing",
        research_root=resolved_root / "research",
        signal_root=resolved_root / "signal_generation",
        signal_arbitration_root=resolved_root / "signal_arbitration",
        backtesting_root=resolved_root / "backtesting",
        ablation_root=resolved_root / "ablation",
        experiments_root=resolved_root / "experiments",
        evaluation_root=resolved_root / "evaluation",
        portfolio_root=resolved_root / "portfolio",
        portfolio_analysis_root=resolved_root / "portfolio_analysis",
        review_root=resolved_root / "review",
        audit_root=resolved_root / "audit",
        monitoring_root=resolved_root / "monitoring",
        timing_root=resolved_root / "timing",
        data_quality_root=resolved_root / "data_quality",
        reconciliation_root=resolved_root / "reconciliation",
        entity_resolution_root=resolved_root / "entity_resolution",
        orchestration_root=resolved_root / "orchestration",
        red_team_root=resolved_root / "red_team",
    )


def resolve_artifact_workspace_from_stage_root(stage_root: Path) -> ArtifactWorkspace:
    """Resolve sibling artifact roots from one stage-specific artifact root."""

    return resolve_artifact_workspace(workspace_root=stage_root.resolve().parent)


def resolve_artifact_workspace_from_path(
    stage_path: Path,
    *,
    stage_directory_name: str,
) -> ArtifactWorkspace:
    """Resolve a workspace from a path nested under one known stage directory."""

    resolved_path = stage_path.resolve()
    for candidate in (resolved_path, *resolved_path.parents):
        if candidate.name == stage_directory_name:
            return resolve_artifact_workspace_from_stage_root(candidate)
    raise ValueError(
        f"Stage path `{stage_path}` does not live under a `{stage_directory_name}` artifact directory."
    )


def ensure_directory_exists(path: Path, *, label: str) -> Path:
    """Require a directory to exist before local artifact access proceeds."""

    if not path.exists():
        raise ValueError(f"{label} `{path}` does not exist.")
    if not path.is_dir():
        raise ValueError(f"{label} `{path}` is not a directory.")
    return path


def ensure_file_exists(path: Path, *, label: str) -> Path:
    """Require a file to exist before local artifact access proceeds."""

    if not path.exists():
        raise ValueError(f"{label} `{path}` does not exist.")
    if not path.is_file():
        raise ValueError(f"{label} `{path}` is not a file.")
    return path


def persist_local_text(
    *,
    root: Path,
    relative_path: Path,
    artifact_id: str,
    raw_text: str,
    data_layer: DataLayer,
    source_reference_ids: list[str],
    clock: Clock,
    transformation_name: str,
) -> ArtifactStorageLocation:
    """Persist one exact text payload and return storage metadata."""

    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(raw_text, encoding="utf-8")
    content_hash = sha256(raw_text.encode("utf-8")).hexdigest()
    return _build_storage_location(
        artifact_id=artifact_id,
        destination=destination,
        data_layer=data_layer,
        content_hash=content_hash,
        source_reference_ids=source_reference_ids,
        clock=clock,
        transformation_name=transformation_name,
    )


def persist_local_model(
    *,
    root: Path,
    category: str,
    artifact_id: str,
    model: StrictModel,
    source_reference_ids: list[str],
    clock: Clock,
    transformation_name: str,
    data_layer: DataLayer = DataLayer.DERIVED,
) -> ArtifactStorageLocation:
    """Persist one typed JSON artifact and return storage metadata."""

    destination = root / category / f"{artifact_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = model.model_dump_json(indent=2)
    destination.write_text(serialized, encoding="utf-8")
    content_hash = sha256(serialized.encode("utf-8")).hexdigest()
    return _build_storage_location(
        artifact_id=artifact_id,
        destination=destination,
        data_layer=data_layer,
        content_hash=content_hash,
        source_reference_ids=source_reference_ids,
        clock=clock,
        transformation_name=transformation_name,
    )


def load_local_models(
    directory: Path,
    model_cls: type[TModel],
    *,
    required: bool = False,
    label: str | None = None,
) -> list[TModel]:
    """Load typed JSON artifacts from one directory when present."""

    return [
        stored.model
        for stored in load_stored_local_models(
            directory,
            model_cls,
            required=required,
            label=label,
        )
    ]


def load_stored_local_models(
    directory: Path,
    model_cls: type[TModel],
    *,
    required: bool = False,
    label: str | None = None,
) -> list[StoredLocalModel[TModel]]:
    """Load typed JSON artifacts plus their filesystem locations."""

    resolved_label = label or "Artifact category"
    if not directory.exists():
        if required:
            raise ValueError(f"{resolved_label} `{directory}` does not exist.")
        return []
    if not directory.is_dir():
        raise ValueError(f"{resolved_label} `{directory}` is not a directory.")
    paths = sorted(path for path in directory.glob("*.json") if path.is_file())
    if required and not paths:
        raise ValueError(f"{resolved_label} `{directory}` does not contain any JSON artifacts.")
    return [
        StoredLocalModel(
            model=model_cls.model_validate_json(path.read_text(encoding="utf-8")),
            path=path,
        )
        for path in paths
    ]


def _build_storage_location(
    *,
    artifact_id: str,
    destination: Path,
    data_layer: DataLayer,
    content_hash: str,
    source_reference_ids: list[str],
    clock: Clock,
    transformation_name: str,
) -> ArtifactStorageLocation:
    """Build one canonical storage record for a persisted local artifact."""

    now = clock.now()
    return ArtifactStorageLocation(
        artifact_storage_location_id=f"store_{content_hash[:24]}",
        artifact_id=artifact_id,
        storage_kind=StorageKind.LOCAL_FILESYSTEM,
        data_layer=data_layer,
        uri=destination.resolve().as_uri(),
        content_hash=content_hash,
        retention_policy="local_development",
        provenance=build_provenance(
            clock=clock,
            transformation_name=transformation_name,
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[artifact_id],
        ),
        created_at=now,
        updated_at=now,
    )
