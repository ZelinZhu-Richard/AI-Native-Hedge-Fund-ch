from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    DataLayer,
    DatasetManifest,
    DatasetPartition,
    DatasetReference,
    DatasetUsageRole,
    DataSnapshot,
    Experiment,
    ExperimentArtifact,
    ExperimentArtifactRole,
    ExperimentConfig,
    ExperimentMetric,
    ExperimentParameter,
    ExperimentParameterValueType,
    ExperimentStatus,
    ProvenanceRecord,
    RunContext,
)

FIXED_NOW = datetime(2026, 3, 18, 9, 0, tzinfo=UTC)


def test_experiment_requires_dataset_references_and_completed_at() -> None:
    with pytest.raises(ValidationError):
        Experiment(
            experiment_id="exp_test",
            name="invalid_experiment",
            objective="This should fail.",
            created_by="unit_test",
            status=ExperimentStatus.COMPLETED,
            experiment_config_id="ecfg_test",
            run_context_id="rctx_test",
            dataset_reference_ids=[],
            started_at=FIXED_NOW,
            completed_at=None,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_experiment_config_requires_hash_and_parameters() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            experiment_config_id="ecfg_test",
            workflow_name="backtesting_workflow",
            workflow_version="0.1.0",
            parameter_hash="",
            parameters=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_experiment_artifact_requires_storage_link_or_uri() -> None:
    with pytest.raises(ValidationError):
        ExperimentArtifact(
            experiment_artifact_id="eart_test",
            experiment_id="exp_test",
            artifact_id="btrun_test",
            artifact_type="BacktestRun",
            artifact_role=ExperimentArtifactRole.OUTPUT,
            produced_at=FIXED_NOW,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_experiment_metric_requires_numeric_value_and_linkage() -> None:
    metric = ExperimentMetric(
        experiment_metric_id="emetric_test",
        experiment_id="exp_test",
        metric_name="net_pnl",
        numeric_value=12.5,
        unit="usd",
        source_artifact_id="psum_test",
        recorded_at=FIXED_NOW,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert metric.source_artifact_id == "psum_test"


def test_data_snapshot_enforces_temporal_ordering() -> None:
    with pytest.raises(ValidationError):
        DataSnapshot(
            data_snapshot_id="snap_test",
            dataset_name="candidate_signals",
            dataset_version="day8",
            dataset_manifest_id="dman_test",
            data_layer=DataLayer.DERIVED,
            snapshot_time=FIXED_NOW,
            event_time_start=FIXED_NOW,
            watermark_time=FIXED_NOW.replace(hour=8),
            ingestion_cutoff_time=FIXED_NOW,
            information_cutoff_time=FIXED_NOW,
            storage_uri="file:///tmp/signals",
            row_count=1,
            schema_version="day8",
            source_families=["candidate_signals"],
            created_by_process="unit_test",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_dataset_manifest_partition_and_reference_validate() -> None:
    partition = DatasetPartition(
        dataset_partition_id="dpart_test",
        dataset_name="candidate_signals",
        partition_key="company_id",
        partition_value="co_test",
        data_snapshot_id="snap_test",
        event_time_start=FIXED_NOW.replace(hour=7),
        event_time_end=FIXED_NOW.replace(hour=8),
        ingestion_cutoff_time=FIXED_NOW,
        row_count=4,
        source_version_ids=["sver_test"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    manifest = DatasetManifest(
        dataset_manifest_id="dman_test",
        dataset_name="candidate_signals",
        dataset_version="day8",
        schema_version="day8",
        data_layer=DataLayer.DERIVED,
        storage_uri="file:///tmp/signals",
        partition_ids=[partition.dataset_partition_id],
        source_families=["candidate_signals"],
        source_version_ids=["sver_test"],
        source_count=1,
        row_count=4,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    dataset_reference = DatasetReference(
        dataset_reference_id="dref_test",
        dataset_name="candidate_signals",
        usage_role=DatasetUsageRole.INPUT,
        dataset_manifest_id=manifest.dataset_manifest_id,
        data_snapshot_id="snap_test",
        data_layer=DataLayer.DERIVED,
        information_cutoff_time=FIXED_NOW,
        schema_version=manifest.schema_version,
        storage_uri="file:///tmp/signals",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    run_context = RunContext(
        run_context_id="rctx_test",
        workflow_name="backtesting_workflow",
        workflow_run_id="btrun_test",
        requested_by="unit_test",
        environment="test",
        artifact_root_uri="file:///tmp/artifacts",
        as_of_time=FIXED_NOW,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    config = ExperimentConfig(
        experiment_config_id="ecfg_test",
        workflow_name="backtesting_workflow",
        workflow_version="0.1.0",
        parameter_hash="abc123",
        parameters=[_parameter()],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert partition.row_count == 4
    assert dataset_reference.dataset_manifest_id == manifest.dataset_manifest_id
    assert run_context.artifact_root_uri.startswith("file://")
    assert config.parameters[0].key == "strategy_name"


def _parameter() -> ExperimentParameter:
    return ExperimentParameter(
        experiment_parameter_id="eparam_test",
        key="strategy_name",
        value_repr="day6_text_signal_exploratory",
        value_type=ExperimentParameterValueType.STRING,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
