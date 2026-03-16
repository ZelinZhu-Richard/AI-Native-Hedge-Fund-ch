from __future__ import annotations

from libraries.config import get_settings
from libraries.schemas.base import ProvenanceRecord
from libraries.time import Clock


def build_provenance(
    *,
    clock: Clock,
    transformation_name: str,
    source_reference_ids: list[str] | None = None,
    upstream_artifact_ids: list[str] | None = None,
    workflow_run_id: str | None = None,
    agent_run_id: str | None = None,
    experiment_id: str | None = None,
    model_name: str | None = None,
    prompt_version: str | None = None,
) -> ProvenanceRecord:
    """Build a baseline provenance record with centralized version metadata."""

    settings = get_settings()
    return ProvenanceRecord(
        source_reference_ids=source_reference_ids or [],
        upstream_artifact_ids=upstream_artifact_ids or [],
        transformation_name=transformation_name,
        transformation_version=settings.app_version,
        config_version=settings.model_registry_version,
        workflow_run_id=workflow_run_id,
        agent_run_id=agent_run_id,
        experiment_id=experiment_id,
        model_name=model_name,
        prompt_version=prompt_version,
        processing_time=clock.now(),
    )
