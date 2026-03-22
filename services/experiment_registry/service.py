from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

from pydantic import Field

from libraries.config import get_settings
from libraries.core import (
    build_provenance,
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    DatasetManifest,
    DatasetPartition,
    DatasetReference,
    Experiment,
    ExperimentArtifact,
    ExperimentConfig,
    ExperimentMetric,
    ExperimentStatus,
    ModelReference,
    QualityDecision,
    RefusalReason,
    RunContext,
    SourceVersion,
    StrictModel,
    ValidationGate,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.utils import make_prefixed_id
from services.data_quality import DataQualityService
from services.experiment_registry.storage import LocalExperimentRegistryArtifactStore


class BeginExperimentRequest(StrictModel):
    """Request to begin and persist a reproducible experiment record."""

    name: str = Field(description="Human-readable experiment name.")
    objective: str = Field(description="Experiment objective or question under study.")
    created_by: str = Field(description="Requester or workflow owner.")
    experiment_config: ExperimentConfig = Field(description="Reproducible experiment config.")
    run_context: RunContext = Field(description="Operational run context.")
    dataset_manifests: list[DatasetManifest] = Field(
        default_factory=list,
        description="Dataset manifests referenced by the experiment.",
    )
    dataset_partitions: list[DatasetPartition] = Field(
        default_factory=list,
        description="Dataset partitions referenced by the experiment.",
    )
    source_versions: list[SourceVersion] = Field(
        default_factory=list,
        description="Source-version records supporting dataset replay.",
    )
    dataset_references: list[DatasetReference] = Field(
        default_factory=list,
        description="Dataset references defining the experiment input boundary.",
    )
    model_references: list[ModelReference] = Field(
        default_factory=list,
        description="Optional model references attached to the experiment.",
    )
    hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="Hypotheses under study when the experiment is research-facing.",
    )
    backtest_run_ids: list[str] = Field(
        default_factory=list,
        description="Backtest runs associated with the experiment.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes attached when the experiment starts.",
    )


class BeginExperimentResponse(StrictModel):
    """Persisted state returned after creating an experiment record."""

    experiment: Experiment = Field(description="Created experiment record.")
    experiment_config: ExperimentConfig = Field(description="Persisted experiment config.")
    run_context: RunContext = Field(description="Persisted run context.")
    dataset_manifests: list[DatasetManifest] = Field(
        default_factory=list,
        description="Persisted dataset manifests.",
    )
    dataset_partitions: list[DatasetPartition] = Field(
        default_factory=list,
        description="Persisted dataset partitions.",
    )
    source_versions: list[SourceVersion] = Field(
        default_factory=list,
        description="Persisted source-version records.",
    )
    dataset_references: list[DatasetReference] = Field(
        default_factory=list,
        description="Persisted dataset references.",
    )
    model_references: list[ModelReference] = Field(
        default_factory=list,
        description="Persisted model references.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Storage locations written while beginning the experiment.",
    )
    validation_gate: ValidationGate | None = Field(
        default=None,
        description="Data-quality gate recorded for experiment metadata when validation ran.",
    )
    quality_decision: QualityDecision | None = Field(
        default=None,
        description="Overall decision emitted by the experiment metadata validation gate.",
    )
    refusal_reason: RefusalReason | None = Field(
        default=None,
        description="Primary refusal reason when experiment creation was blocked.",
    )


class FinalizeExperimentRequest(StrictModel):
    """Request to finalize an experiment after its workflow completes."""

    experiment: Experiment = Field(description="Existing experiment record to finalize.")
    experiment_artifacts: list[ExperimentArtifact] = Field(
        default_factory=list,
        description="Artifacts produced or consumed by the experiment.",
    )
    experiment_metrics: list[ExperimentMetric] = Field(
        default_factory=list,
        description="Metrics recorded for the experiment.",
    )
    status: ExperimentStatus = Field(
        default=ExperimentStatus.COMPLETED,
        description="Final experiment status.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional completion notes to append to the experiment.",
    )


class FinalizeExperimentResponse(StrictModel):
    """Persisted state returned after finalizing an experiment."""

    experiment: Experiment = Field(description="Updated experiment record.")
    experiment_artifacts: list[ExperimentArtifact] = Field(
        default_factory=list,
        description="Persisted experiment-artifact records.",
    )
    experiment_metrics: list[ExperimentMetric] = Field(
        default_factory=list,
        description="Persisted experiment-metric records.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Storage locations written while finalizing the experiment.",
    )


class ExperimentRegistryService(BaseService):
    """Record reproducible experiment metadata, dataset references, and outputs."""

    capability_name = "experiment_registry"
    capability_description = "Records reproducible experiment configs, dataset references, artifacts, and metrics."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["ExperimentConfig", "RunContext", "DatasetReference"],
            produces=["Experiment", "ExperimentArtifact", "ExperimentMetric"],
            api_routes=[],
        )

    def begin_experiment(
        self,
        request: BeginExperimentRequest,
        *,
        output_root: Path | None = None,
    ) -> BeginExperimentResponse:
        """Create and persist a running experiment record plus its reproducibility metadata."""

        experiments_root = output_root or (get_settings().resolved_artifact_root / "experiments")
        workspace = (
            resolve_artifact_workspace_from_stage_root(experiments_root)
            if output_root is not None
            else resolve_artifact_workspace(workspace_root=get_settings().resolved_artifact_root)
        )
        validation_result = DataQualityService(clock=self.clock).validate_experiment_metadata(
            experiment_name=request.name,
            created_by=request.created_by,
            experiment_config=request.experiment_config,
            dataset_references=request.dataset_references,
            workflow_run_id=request.run_context.workflow_run_id,
            requested_by=request.created_by,
            output_root=workspace.data_quality_root,
        )

        store = LocalExperimentRegistryArtifactStore(
            root=experiments_root,
            clock=self.clock,
        )
        experiment_id = make_prefixed_id("exp")
        now = self.clock.now()
        storage_locations: list[ArtifactStorageLocation] = list(validation_result.storage_locations)

        storage_locations.append(
            self._persist_model(
                store=store,
                category="experiment_configs",
                model=request.experiment_config,
            )
        )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="run_contexts",
                model=request.run_context,
            )
        )
        for source_version in request.source_versions:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="source_versions",
                    model=source_version,
                )
            )
        for partition in request.dataset_partitions:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="dataset_partitions",
                    model=partition,
                )
            )
        for manifest in request.dataset_manifests:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="dataset_manifests",
                    model=manifest,
                )
            )
        for dataset_reference in request.dataset_references:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="dataset_references",
                    model=dataset_reference,
                )
            )
        for model_reference in request.model_references:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="model_references",
                    model=model_reference,
                )
            )

        experiment = Experiment(
            experiment_id=experiment_id,
            name=request.name,
            objective=request.objective,
            created_by=request.created_by,
            status=ExperimentStatus.RUNNING,
            experiment_config_id=request.experiment_config.experiment_config_id,
            run_context_id=request.run_context.run_context_id,
            dataset_reference_ids=[
                dataset_reference.dataset_reference_id
                for dataset_reference in request.dataset_references
            ],
            model_reference_ids=[
                model_reference.model_reference_id
                for model_reference in request.model_references
            ],
            hypothesis_ids=request.hypothesis_ids,
            backtest_run_ids=request.backtest_run_ids,
            experiment_artifact_ids=[],
            experiment_metric_ids=[],
            started_at=now,
            completed_at=None,
            notes=request.notes,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="experiment_registry_begin_experiment",
                source_reference_ids=_collect_source_reference_ids(
                    models=[
                        request.experiment_config,
                        request.run_context,
                        *request.source_versions,
                        *request.dataset_partitions,
                        *request.dataset_manifests,
                        *request.dataset_references,
                        *request.model_references,
                    ]
                ),
                upstream_artifact_ids=[
                    request.experiment_config.experiment_config_id,
                    request.run_context.run_context_id,
                    *[
                        source_version.source_version_id
                        for source_version in request.source_versions
                    ],
                    *[
                        partition.dataset_partition_id
                        for partition in request.dataset_partitions
                    ],
                    *[
                        manifest.dataset_manifest_id
                        for manifest in request.dataset_manifests
                    ],
                    *[
                        dataset_reference.dataset_reference_id
                        for dataset_reference in request.dataset_references
                    ],
                    *[
                        model_reference.model_reference_id
                        for model_reference in request.model_references
                    ],
                ],
                workflow_run_id=request.run_context.workflow_run_id,
                notes=request.notes,
            ),
            created_at=now,
            updated_at=now,
        )
        storage_locations.append(
            self._persist_model(store=store, category="experiments", model=experiment)
        )

        return BeginExperimentResponse(
            experiment=experiment,
            experiment_config=request.experiment_config,
            run_context=request.run_context,
            dataset_manifests=request.dataset_manifests,
            dataset_partitions=request.dataset_partitions,
            source_versions=request.source_versions,
            dataset_references=request.dataset_references,
            model_references=request.model_references,
            storage_locations=storage_locations,
            validation_gate=validation_result.validation_gate,
            quality_decision=validation_result.validation_gate.decision,
            refusal_reason=validation_result.validation_gate.refusal_reason,
        )

    def finalize_experiment(
        self,
        request: FinalizeExperimentRequest,
        *,
        output_root: Path | None = None,
    ) -> FinalizeExperimentResponse:
        """Persist artifacts and metrics, then finalize the experiment record."""

        store = LocalExperimentRegistryArtifactStore(
            root=output_root or (get_settings().resolved_artifact_root / "experiments"),
            clock=self.clock,
        )
        storage_locations: list[ArtifactStorageLocation] = []
        for experiment_artifact in request.experiment_artifacts:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="experiment_artifacts",
                    model=experiment_artifact,
                )
            )
        for experiment_metric in request.experiment_metrics:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="experiment_metrics",
                    model=experiment_metric,
                )
            )

        now = self.clock.now()
        experiment = request.experiment.model_copy(
            update={
                "status": request.status,
                "experiment_artifact_ids": [
                    experiment_artifact.experiment_artifact_id
                    for experiment_artifact in request.experiment_artifacts
                ],
                "experiment_metric_ids": [
                    experiment_metric.experiment_metric_id
                    for experiment_metric in request.experiment_metrics
                ],
                "completed_at": now,
                "notes": [*request.experiment.notes, *request.notes],
                "updated_at": now,
                "provenance": request.experiment.provenance.model_copy(
                    update={
                        "upstream_artifact_ids": [
                            *request.experiment.provenance.upstream_artifact_ids,
                            *[
                                experiment_artifact.experiment_artifact_id
                                for experiment_artifact in request.experiment_artifacts
                            ],
                            *[
                                experiment_metric.experiment_metric_id
                                for experiment_metric in request.experiment_metrics
                            ],
                        ],
                        "processing_time": now,
                        "notes": [*request.experiment.provenance.notes, *request.notes],
                    }
                ),
            }
        )
        storage_locations.append(
            self._persist_model(store=store, category="experiments", model=experiment)
        )

        return FinalizeExperimentResponse(
            experiment=experiment,
            experiment_artifacts=request.experiment_artifacts,
            experiment_metrics=request.experiment_metrics,
            storage_locations=storage_locations,
        )

    def _persist_model(
        self,
        *,
        store: LocalExperimentRegistryArtifactStore,
        category: str,
        model: StrictModel,
    ) -> ArtifactStorageLocation:
        """Persist one typed experiment-registry artifact."""

        artifact_id = _artifact_id(model=model)
        source_reference_ids = cast(_ProvenancedModel, model).provenance.source_reference_ids
        return store.persist_model(
            artifact_id=artifact_id,
            category=category,
            model=model,
            source_reference_ids=source_reference_ids,
        )


class _ProvenancedModel(Protocol):
    provenance: ProvenanceRecord


def _artifact_id(*, model: StrictModel) -> str:
    """Resolve the canonical identifier field for a strict model."""

    for field_name in type(model).model_fields:
        if field_name.endswith("_id"):
            value = getattr(model, field_name, None)
            if isinstance(value, str):
                return value
    raise ValueError(f"Could not resolve artifact ID for model type `{type(model).__name__}`.")


def _collect_source_reference_ids(*, models: list[StrictModel]) -> list[str]:
    """Collect unique source-reference identifiers from a list of typed models."""

    source_reference_ids: list[str] = []
    for model in models:
        source_reference_ids.extend(cast(_ProvenancedModel, model).provenance.source_reference_ids)
    return list(dict.fromkeys(source_reference_ids))
