from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from libraries.core import (
    load_local_models,
    load_stored_local_models,
    persist_local_model,
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.schemas import StrictModel
from libraries.time import FrozenClock

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


class ExampleArtifact(StrictModel):
    """Minimal strict model used to validate local artifact helpers."""

    example_artifact_id: str = Field(description="Test artifact identifier.")
    value: str = Field(description="Test payload value.")


def test_resolve_artifact_workspace_exposes_standard_stage_roots(tmp_path: Path) -> None:
    workspace = resolve_artifact_workspace(workspace_root=tmp_path / "workspace")

    assert workspace.root == (tmp_path / "workspace").resolve()
    assert workspace.ingestion_root == workspace.root / "ingestion"
    assert workspace.signal_root == workspace.root / "signal_generation"
    assert workspace.portfolio_analysis_root == workspace.root / "portfolio_analysis"
    assert workspace.orchestration_root == workspace.root / "orchestration"


def test_resolve_artifact_workspace_from_stage_root_uses_parent_workspace(tmp_path: Path) -> None:
    stage_root = tmp_path / "custom_run" / "signal_generation"
    workspace = resolve_artifact_workspace_from_stage_root(stage_root)

    assert workspace.root == (tmp_path / "custom_run").resolve()
    assert workspace.signal_root == stage_root.resolve()
    assert workspace.research_root == workspace.root / "research"


def test_persist_and_load_local_models_preserves_paths_and_uris(tmp_path: Path) -> None:
    model = ExampleArtifact(example_artifact_id="example_1", value="hello")

    storage_location = persist_local_model(
        root=tmp_path,
        category="examples",
        artifact_id=model.example_artifact_id,
        model=model,
        source_reference_ids=["src_example"],
        clock=FrozenClock(FIXED_NOW),
        transformation_name="unit_test_local_artifact_store",
    )

    loaded_models = load_local_models(
        tmp_path / "examples",
        ExampleArtifact,
        required=True,
        label="Example category",
    )
    stored_models = load_stored_local_models(
        tmp_path / "examples",
        ExampleArtifact,
        required=True,
        label="Example category",
    )

    assert loaded_models == [model]
    assert stored_models[0].model == model
    assert stored_models[0].path == tmp_path / "examples" / "example_1.json"
    assert stored_models[0].uri.startswith("file://")
    assert storage_location.artifact_id == model.example_artifact_id
    assert storage_location.uri == stored_models[0].uri
