from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol, cast

from pydantic import Field

from libraries.config import get_settings
from libraries.core import (
    build_provenance,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AblationConfig,
    AblationResult,
    AblationVariantResult,
    ArtifactStorageLocation,
    AuditOutcome,
    BacktestConfig,
    BacktestRun,
    BenchmarkReference,
    ComparisonSummary,
    CoverageSummary,
    DatasetManifest,
    DatasetPartition,
    DatasetReference,
    DatasetUsageRole,
    DataSnapshot,
    DecisionCutoff,
    EvaluationMetric,
    EvaluationReport,
    Experiment,
    ExperimentArtifact,
    ExperimentArtifactRole,
    ExperimentConfig,
    ExperimentMetric,
    ExperimentParameter,
    ExperimentParameterValueType,
    ExperimentStatus,
    FailureCase,
    PerformanceSummary,
    PipelineEventType,
    RobustnessCheck,
    RunContext,
    SignalCalibration,
    SignalConflict,
    SimulationEvent,
    SourceVersion,
    StrategyDecision,
    StrategySpec,
    StrategyVariant,
    StrictModel,
    TimingAnomaly,
    WorkflowStatus,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.utils import make_canonical_id, make_prefixed_id
from services.audit import AuditEventRequest, AuditLoggingService
from services.backtesting.ablation import (
    build_parent_experiment_artifacts,
    build_parent_experiment_config,
    build_parent_experiment_metrics,
    build_parent_run_context,
    build_strategy_input_snapshots,
    build_strategy_specs,
    build_variant_backtest_config,
    build_variant_backtest_inputs,
    load_strategy_inputs,
    materialize_variant_signals,
    sort_variant_results,
)
from services.backtesting.loaders import LoadedBacktestInputs, load_backtest_inputs
from services.backtesting.simulation import run_backtest_simulation
from services.backtesting.storage import LocalBacktestArtifactStore
from services.evaluation import (
    AblationVariantRunEvaluationInput,
    EvaluateStrategyAblationRequest,
    EvaluationService,
)
from services.experiment_registry import (
    BeginExperimentRequest,
    ExperimentRegistryService,
    FinalizeExperimentRequest,
)
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.signal_arbitration.loaders import load_latest_signal_bundle
from services.signal_arbitration.storage import load_models as load_signal_arbitration_models
from services.timing import TimingService


class BacktestRequest(StrictModel):
    """Request to evaluate a signal family under explicit temporal controls."""

    experiment_name: str = Field(description="Human-readable experiment name.")
    signal_family: str = Field(description="Signal family to evaluate.")
    universe_definition: str = Field(description="Point-in-time universe definition.")
    test_start: datetime = Field(description="Out-of-sample start timestamp.")
    test_end: datetime = Field(description="Out-of-sample end timestamp.")
    requested_by: str = Field(description="Requester identifier.")


class BacktestResponse(StrictModel):
    """Response returned after accepting a queued backtest request."""

    backtest_run_id: str = Field(description="Reserved backtest run identifier.")
    status: str = Field(description="Operational status.")
    queued_at: datetime = Field(description="UTC timestamp when the backtest was queued.")
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes or guardrail reminders.",
    )


class RunBacktestWorkflowRequest(StrictModel):
    """Explicit local request to run the exploratory backtest workflow."""

    signal_root: Path = Field(description="Root path containing persisted signal artifacts.")
    signal_arbitration_root: Path | None = Field(
        default=None,
        description="Optional root path containing persisted signal arbitration artifacts.",
    )
    feature_root: Path = Field(description="Root path containing persisted feature artifacts.")
    price_fixture_path: Path = Field(description="Path to the synthetic daily price fixture.")
    loaded_inputs: LoadedBacktestInputs | None = Field(
        default=None,
        description="Optional preloaded comparable inputs used by internal workflows such as strategy ablations.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional output root for persisted backtesting artifacts.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when the signal root contains multiple companies.",
    )
    backtest_config: BacktestConfig = Field(description="Reproducible backtest configuration.")
    record_experiment: bool = Field(
        default=True,
        description="Whether to record a reproducibility-complete experiment for the run.",
    )
    experiment_name: str | None = Field(
        default=None,
        description="Optional experiment name override for the reproducibility registry.",
    )
    experiment_objective: str | None = Field(
        default=None,
        description="Optional experiment objective override for the reproducibility registry.",
    )
    experiment_root: Path | None = Field(
        default=None,
        description="Optional output root for persisted experiment-registry artifacts.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunBacktestWorkflowResponse(StrictModel):
    """Result of the deterministic exploratory backtesting workflow."""

    backtest_run: BacktestRun = Field(description="Completed exploratory backtest run artifact.")
    backtest_config: BacktestConfig = Field(description="Reproducible backtest configuration.")
    data_snapshots: list[DataSnapshot] = Field(
        default_factory=list,
        description="Signal and price snapshots used by the run.",
    )
    strategy_decisions: list[StrategyDecision] = Field(
        default_factory=list,
        description="Point-in-time decisions emitted by the run.",
    )
    simulation_events: list[SimulationEvent] = Field(
        default_factory=list,
        description="Simulation events emitted by the run.",
    )
    decision_cutoffs: list[DecisionCutoff] = Field(
        default_factory=list,
        description="Decision cutoffs used to evaluate point-in-time eligibility.",
    )
    timing_anomalies: list[TimingAnomaly] = Field(
        default_factory=list,
        description="Structured timing anomalies observed during the run.",
    )
    performance_summary: PerformanceSummary = Field(
        description="Mechanical performance summary for the run."
    )
    benchmark_references: list[BenchmarkReference] = Field(
        default_factory=list,
        description="Mechanical benchmarks emitted alongside the run.",
    )
    experiment: Experiment | None = Field(
        default=None,
        description="Optional experiment record associated with the run.",
    )
    experiment_config: ExperimentConfig | None = Field(
        default=None,
        description="Optional experiment configuration recorded for reproducibility.",
    )
    dataset_references: list[DatasetReference] = Field(
        default_factory=list,
        description="Dataset references used to reproduce the run.",
    )
    experiment_artifacts: list[ExperimentArtifact] = Field(
        default_factory=list,
        description="Structured experiment-artifact references recorded for the run.",
    )
    experiment_metrics: list[ExperimentMetric] = Field(
        default_factory=list,
        description="Structured experiment metrics recorded for the run.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing assumptions or skipped work.",
    )


class RunStrategyAblationWorkflowRequest(StrictModel):
    """Explicit local request to compare multiple baseline strategy variants honestly."""

    signal_root: Path = Field(description="Root path containing persisted research signal artifacts.")
    signal_arbitration_root: Path | None = Field(
        default=None,
        description="Optional root path containing persisted signal arbitration artifacts.",
    )
    feature_root: Path = Field(description="Root path containing persisted feature artifacts.")
    price_fixture_path: Path = Field(description="Path to the shared synthetic daily price fixture.")
    output_root: Path | None = Field(
        default=None,
        description="Optional root for persisted ablation artifacts.",
    )
    experiment_root: Path | None = Field(
        default=None,
        description="Optional root for persisted experiment-registry artifacts.",
    )
    evaluation_root: Path | None = Field(
        default=None,
        description="Optional root for persisted evaluation artifacts.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when roots contain multiple companies.",
    )
    ablation_config: AblationConfig = Field(
        description="Shared reproducible configuration for the ablation run."
    )


class RunStrategyAblationWorkflowResponse(StrictModel):
    """Result of the deterministic Day 9 strategy ablation workflow."""

    strategy_specs: list[StrategySpec] = Field(
        default_factory=list,
        description="Strategy-family specifications used by the run.",
    )
    strategy_variants: list[StrategyVariant] = Field(
        default_factory=list,
        description="Concrete strategy variants compared by the run.",
    )
    ablation_result: AblationResult = Field(
        description="Structured comparison result across all configured variants."
    )
    variant_backtest_runs: list[BacktestRun] = Field(
        default_factory=list,
        description="Backtest runs recorded for each compared variant.",
    )
    experiment: Experiment | None = Field(
        default=None,
        description="Optional parent experiment recorded for the ablation harness.",
    )
    evaluation_report: EvaluationReport | None = Field(
        default=None,
        description="Optional structured evaluation report for the ablation output.",
    )
    evaluation_metrics: list[EvaluationMetric] = Field(
        default_factory=list,
        description="Evaluation metrics recorded for the ablation output.",
    )
    failure_cases: list[FailureCase] = Field(
        default_factory=list,
        description="Failure cases recorded for the ablation output.",
    )
    robustness_checks: list[RobustnessCheck] = Field(
        default_factory=list,
        description="Robustness checks recorded for the ablation output.",
    )
    comparison_summary: ComparisonSummary | None = Field(
        default=None,
        description="Optional comparison summary recorded for the ablation output.",
    )
    coverage_summaries: list[CoverageSummary] = Field(
        default_factory=list,
        description="Coverage summaries recorded for the ablation output.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the ablation workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing assumptions and comparison caveats.",
    )


class BacktestingService(BaseService):
    """Run temporally disciplined exploratory backtests against persisted artifacts."""

    capability_name = "backtesting"
    capability_description = "Runs exploratory backtests with explicit temporal cutoffs, synthetic fixtures, and experiment recording."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Signal", "Feature", "DataSnapshot", "BacktestConfig"],
            produces=[
                "BacktestRun",
                "StrategyDecision",
                "SimulationEvent",
                "PerformanceSummary",
                "BenchmarkReference",
                "Experiment",
                "DatasetReference",
            ],
            api_routes=[],
        )

    def run_backtest(self, request: BacktestRequest) -> BacktestResponse:
        """Queue a backtest for future execution."""

        return BacktestResponse(
            backtest_run_id=make_prefixed_id("btrun"),
            status="queued",
            queued_at=self.clock.now(),
            notes=[
                "Day 6 queued backtests remain exploratory-only.",
                "Use run_backtest_workflow() for the deterministic local backtesting path.",
            ],
        )

    def run_backtest_workflow(
        self,
        request: RunBacktestWorkflowRequest,
    ) -> RunBacktestWorkflowResponse:
        """Execute the deterministic Day 6 exploratory backtesting workflow."""

        backtest_run_id = make_prefixed_id("btrun")
        inputs = request.loaded_inputs or load_backtest_inputs(
            signal_root=request.signal_root,
            feature_root=request.feature_root,
            price_fixture_path=request.price_fixture_path,
            company_id=request.company_id,
        )
        result = run_backtest_simulation(
            inputs=inputs,
            config=request.backtest_config,
            clock=self.clock,
            workflow_run_id=backtest_run_id,
            backtest_run_id=backtest_run_id,
        )
        workspace = resolve_artifact_workspace_from_stage_root(request.feature_root)
        output_root = request.output_root or workspace.backtesting_root
        experiment_root = request.experiment_root or workspace.experiments_root
        audit_root = workspace.audit_root
        timing_root = workspace.timing_root
        store = LocalBacktestArtifactStore(root=output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
        experiment: Experiment | None = None
        experiment_config: ExperimentConfig | None = None
        dataset_references: list[DatasetReference] = []
        experiment_artifacts: list[ExperimentArtifact] = []
        experiment_metrics: list[ExperimentMetric] = []

        storage_locations.append(
            store.persist_model(
                artifact_id=request.backtest_config.backtest_config_id,
                category="configs",
                model=request.backtest_config,
                source_reference_ids=request.backtest_config.provenance.source_reference_ids,
            )
        )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="configs",
                model=request.backtest_config.execution_assumption,
            )
        )
        data_snapshots = list(result.data_snapshots)
        if request.record_experiment:
            data_snapshots = self._attach_manifest_ids_to_snapshots(
                company_id=inputs.company_id,
                snapshots=data_snapshots,
            )
        snapshot_storage_locations: list[ArtifactStorageLocation] = []
        for snapshot in data_snapshots:
            location = self._persist_model(store=store, category="snapshots", model=snapshot)
            snapshot_storage_locations.append(location)
            storage_locations.append(location)
        for decision_cutoff in result.decision_cutoffs:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="decision_cutoffs",
                    model=decision_cutoff,
                )
            )
        if result.timing_anomalies:
            timing_response = TimingService(clock=self.clock).persist_anomalies(
                anomalies=result.timing_anomalies,
                output_root=timing_root,
            )
            storage_locations.extend(timing_response.storage_locations)
        if request.record_experiment:
            (
                data_snapshots,
                dataset_manifests,
                dataset_partitions,
                source_versions,
                dataset_references,
            ) = self._build_dataset_registry_records(
                company_id=inputs.company_id,
                signal_root=request.signal_root,
                price_fixture_path=request.price_fixture_path,
                snapshots=data_snapshots,
                backtest_config=request.backtest_config,
                workflow_run_id=backtest_run_id,
                snapshot_storage_locations_by_id={
                    location.artifact_id: location for location in snapshot_storage_locations
                },
            )
            experiment_config = self._build_experiment_config(
                backtest_config=request.backtest_config,
                workflow_run_id=backtest_run_id,
            )
            run_context = self._build_run_context(
                workflow_run_id=backtest_run_id,
                requested_by=request.requested_by,
                artifact_root=output_root,
                as_of_time=max(
                    snapshot.information_cutoff_time or snapshot.snapshot_time
                    for snapshot in data_snapshots
                ),
            )
            begin_response = ExperimentRegistryService(clock=self.clock).begin_experiment(
                BeginExperimentRequest(
                    name=(
                        request.experiment_name
                        or f"{request.backtest_config.strategy_name}:{request.backtest_config.test_start.isoformat()}:{request.backtest_config.test_end.isoformat()}"
                    ),
                    objective=(
                        request.experiment_objective
                        or (
                            "Record a reproducible exploratory backtest for "
                            f"{request.backtest_config.signal_family}:{request.backtest_config.ablation_view.value}."
                        )
                    ),
                    created_by=request.requested_by,
                    experiment_config=experiment_config,
                    run_context=run_context,
                    dataset_manifests=dataset_manifests,
                    dataset_partitions=dataset_partitions,
                    source_versions=source_versions,
                    dataset_references=dataset_references,
                    backtest_run_ids=[result.backtest_run.backtest_run_id],
                    notes=[
                        "Day 8 experiment recording is metadata-first and backtest-integrated.",
                        "Backtest runs remain exploratory-only even when registered as experiments.",
                    ],
                ),
                output_root=experiment_root,
            )
            experiment = begin_response.experiment
            storage_locations.extend(begin_response.storage_locations)
        for decision in result.strategy_decisions:
            storage_locations.append(
                self._persist_model(store=store, category="decisions", model=decision)
            )
        for event in result.simulation_events:
            storage_locations.append(
                self._persist_model(store=store, category="events", model=event)
            )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="performance_summaries",
                model=result.performance_summary,
            )
        )
        for benchmark in result.benchmark_references:
            storage_locations.append(
                self._persist_model(store=store, category="benchmarks", model=benchmark)
            )
        backtest_run = result.backtest_run
        if experiment is not None:
            now = self.clock.now()
            backtest_run = result.backtest_run.model_copy(
                update={
                    "experiment_id": experiment.experiment_id,
                    "updated_at": now,
                    "provenance": result.backtest_run.provenance.model_copy(
                        update={"experiment_id": experiment.experiment_id, "processing_time": now}
                    ),
                }
            )
        storage_locations.append(
            self._persist_model(store=store, category="runs", model=backtest_run)
        )

        if experiment is not None:
            storage_by_artifact_id = {
                location.artifact_id: location for location in storage_locations
            }
            experiment_artifacts = self._build_experiment_artifacts(
                experiment=experiment,
                backtest_run=backtest_run,
                snapshots=data_snapshots,
                performance_summary=result.performance_summary,
                benchmark_references=result.benchmark_references,
                storage_by_artifact_id=storage_by_artifact_id,
                workflow_run_id=backtest_run_id,
            )
            experiment_artifacts.extend(
                self._build_signal_arbitration_experiment_artifacts(
                    experiment=experiment,
                    signal_arbitration_root=request.signal_arbitration_root,
                    company_id=inputs.company_id,
                    as_of_time=max(
                        snapshot.information_cutoff_time or snapshot.snapshot_time
                        for snapshot in data_snapshots
                    ),
                    workflow_run_id=backtest_run_id,
                )
            )
            experiment_metrics = self._build_experiment_metrics(
                experiment=experiment,
                performance_summary=result.performance_summary,
                benchmark_references=result.benchmark_references,
                workflow_run_id=backtest_run_id,
            )
            finalize_response = ExperimentRegistryService(clock=self.clock).finalize_experiment(
                FinalizeExperimentRequest(
                    experiment=experiment,
                    experiment_artifacts=experiment_artifacts,
                    experiment_metrics=experiment_metrics,
                    status=ExperimentStatus.COMPLETED,
                    notes=[
                        f"backtest_run_id={backtest_run.backtest_run_id}",
                        *[
                            f"timing_anomaly_id={anomaly.timing_anomaly_id}"
                            for anomaly in result.timing_anomalies
                        ],
                        *[
                            f"decision_cutoff_id={cutoff.decision_cutoff_id}"
                            for cutoff in result.decision_cutoffs
                        ],
                        "Experiment finalized from deterministic backtest workflow output.",
                    ],
                ),
                output_root=experiment_root,
            )
            experiment = finalize_response.experiment
            storage_locations.extend(finalize_response.storage_locations)

        notes = [f"requested_by={request.requested_by}", *result.notes]
        if result.timing_anomalies:
            notes.append(f"timing_anomaly_count={len(result.timing_anomalies)}")
        if experiment is not None:
            notes.append(f"experiment_id={experiment.experiment_id}")
        else:
            notes.append("experiment_recording=disabled")
        audit_response = AuditLoggingService(clock=self.clock).record_event(
            AuditEventRequest(
                event_type="backtest_workflow_completed",
                actor_type="service",
                actor_id="backtesting",
                target_type="backtest_run",
                target_id=backtest_run.backtest_run_id,
                action="completed",
                outcome=AuditOutcome.SUCCESS,
                reason="Exploratory backtest workflow completed.",
                request_id=backtest_run.backtest_run_id,
                related_artifact_ids=[
                    request.backtest_config.backtest_config_id,
                    *[snapshot.data_snapshot_id for snapshot in data_snapshots],
                    *[decision.strategy_decision_id for decision in result.strategy_decisions],
                    *[event.simulation_event_id for event in result.simulation_events],
                    result.performance_summary.performance_summary_id,
                    *[benchmark.benchmark_reference_id for benchmark in result.benchmark_references],
                    *[dataset_reference.dataset_reference_id for dataset_reference in dataset_references],
                    *(
                        [experiment.experiment_id, experiment.experiment_config_id]
                        if experiment is not None
                        else []
                    ),
                ],
                notes=notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        if experiment is not None:
            experiment_audit_response = AuditLoggingService(clock=self.clock).record_event(
                AuditEventRequest(
                    event_type="experiment_completed",
                    actor_type="service",
                    actor_id="experiment_registry",
                    target_type="experiment",
                    target_id=experiment.experiment_id,
                    action="completed",
                    outcome=AuditOutcome.SUCCESS,
                    reason="Backtest experiment registry records were persisted.",
                    request_id=backtest_run.backtest_run_id,
                    related_artifact_ids=[
                        experiment.experiment_config_id,
                        experiment.run_context_id,
                        *experiment.dataset_reference_ids,
                        *experiment.experiment_artifact_ids,
                        *experiment.experiment_metric_ids,
                    ],
                    notes=notes,
                ),
                output_root=audit_root,
            )
            storage_locations.append(experiment_audit_response.storage_location)

        return RunBacktestWorkflowResponse(
            backtest_run=backtest_run,
            backtest_config=request.backtest_config,
            data_snapshots=data_snapshots,
            strategy_decisions=result.strategy_decisions,
            simulation_events=result.simulation_events,
            decision_cutoffs=result.decision_cutoffs,
            timing_anomalies=result.timing_anomalies,
            performance_summary=result.performance_summary,
            benchmark_references=result.benchmark_references,
            experiment=experiment,
            experiment_config=experiment_config,
            dataset_references=dataset_references,
            experiment_artifacts=experiment_artifacts,
            experiment_metrics=experiment_metrics,
            storage_locations=storage_locations,
            notes=notes,
        )

    def run_strategy_ablation_workflow(
        self,
        request: RunStrategyAblationWorkflowRequest,
    ) -> RunStrategyAblationWorkflowResponse:
        """Execute the deterministic Day 9 baseline and ablation workflow."""

        ablation_run_id = make_prefixed_id("ablation")
        workspace = resolve_artifact_workspace_from_stage_root(request.feature_root)
        output_root = request.output_root or workspace.ablation_root
        experiment_root = request.experiment_root or workspace.experiments_root
        evaluation_root = request.evaluation_root or workspace.evaluation_root
        audit_root = workspace.audit_root
        monitoring_root = workspace.monitoring_root
        monitoring_service = MonitoringService(clock=self.clock)
        started_at = self.clock.now()
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="strategy_ablation",
                workflow_run_id=ablation_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message=(
                    f"Strategy ablation started for `{request.ablation_config.name}`."
                ),
                related_artifact_ids=[
                    request.ablation_config.ablation_config_id,
                    request.ablation_config.evaluation_slice.evaluation_slice_id,
                ],
                notes=[f"requested_by={request.ablation_config.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        try:
            response = self._run_strategy_ablation_workflow_impl(
                request,
                ablation_run_id=ablation_run_id,
                output_root=output_root,
                experiment_root=experiment_root,
                evaluation_root=evaluation_root,
                audit_root=audit_root,
            )
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="strategy_ablation",
                    workflow_run_id=ablation_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=(
                        f"Strategy ablation failed for `{request.ablation_config.name}`: {exc}"
                    ),
                    related_artifact_ids=[
                        request.ablation_config.ablation_config_id,
                        request.ablation_config.evaluation_slice.evaluation_slice_id,
                    ],
                    notes=[f"requested_by={request.ablation_config.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="strategy_ablation",
                    workflow_run_id=ablation_run_id,
                    service_name=self.capability_name,
                    requested_by=request.ablation_config.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=[],
                    produced_artifact_ids=[
                        request.ablation_config.ablation_config_id,
                        request.ablation_config.evaluation_slice.evaluation_slice_id,
                    ],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=[
                        "Strategy ablation failed before a complete comparison result was persisted."
                    ],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise

        summary_status, attention_reasons = monitoring_service.summarize_ablation_monitoring(
            evaluation_report=response.evaluation_report,
            failure_cases=response.failure_cases,
            robustness_checks=response.robustness_checks,
        )
        completed_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="strategy_ablation",
                workflow_run_id=ablation_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_COMPLETED,
                status=WorkflowStatus.SUCCEEDED,
                message=(
                    f"Strategy ablation completed for `{request.ablation_config.name}` "
                    f"across {len(response.variant_backtest_runs)} variants."
                ),
                related_artifact_ids=[
                    response.ablation_result.ablation_result_id,
                    *[run.backtest_run_id for run in response.variant_backtest_runs],
                    *(
                        [response.experiment.experiment_id]
                        if response.experiment is not None
                        else []
                    ),
                    *(
                        [response.evaluation_report.evaluation_report_id]
                        if response.evaluation_report is not None
                        else []
                    ),
                ],
                notes=[f"requested_by={request.ablation_config.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        pipeline_event_ids = [
            start_event.pipeline_event.pipeline_event_id,
            completed_event.pipeline_event.pipeline_event_id,
        ]
        if summary_status is WorkflowStatus.ATTENTION_REQUIRED:
            attention_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="strategy_ablation",
                    workflow_run_id=ablation_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.ATTENTION_REQUIRED,
                    status=WorkflowStatus.ATTENTION_REQUIRED,
                    message=(
                        attention_reasons[0]
                        if attention_reasons
                        else "Ablation completed with warnings or failures that require review."
                    ),
                    related_artifact_ids=[
                        response.ablation_result.ablation_result_id,
                        *(
                            [response.evaluation_report.evaluation_report_id]
                            if response.evaluation_report is not None
                            else []
                        ),
                    ],
                    notes=[f"requested_by={request.ablation_config.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            pipeline_event_ids.append(attention_event.pipeline_event.pipeline_event_id)
        monitoring_service.record_run_summary(
            RecordRunSummaryRequest(
                workflow_name="strategy_ablation",
                workflow_run_id=ablation_run_id,
                service_name=self.capability_name,
                requested_by=request.ablation_config.requested_by,
                status=summary_status,
                started_at=started_at,
                completed_at=self.clock.now(),
                storage_locations=response.storage_locations,
                produced_artifact_ids=[
                    response.ablation_result.ablation_result_id,
                    *[spec.strategy_spec_id for spec in response.strategy_specs],
                    *[
                        strategy_variant.strategy_variant_id
                        for strategy_variant in response.strategy_variants
                    ],
                    *[run.backtest_run_id for run in response.variant_backtest_runs],
                    *(
                        [response.experiment.experiment_id]
                        if response.experiment is not None
                        else []
                    ),
                    *(
                        [response.evaluation_report.evaluation_report_id]
                        if response.evaluation_report is not None
                        else []
                    ),
                    *(
                        [response.comparison_summary.comparison_summary_id]
                        if response.comparison_summary is not None
                        else []
                    ),
                ],
                pipeline_event_ids=pipeline_event_ids,
                attention_reasons=attention_reasons,
                notes=response.notes,
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        return response

    def _run_strategy_ablation_workflow_impl(
        self,
        request: RunStrategyAblationWorkflowRequest,
        *,
        ablation_run_id: str,
        output_root: Path,
        experiment_root: Path,
        evaluation_root: Path,
        audit_root: Path,
    ) -> RunStrategyAblationWorkflowResponse:
        """Execute the deterministic Day 9 baseline and ablation workflow."""

        store = LocalBacktestArtifactStore(root=output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
        notes: list[str] = [
            "Day 9 ablation rows are mechanical comparisons, not validated performance claims."
        ]

        strategy_inputs = load_strategy_inputs(
            signal_root=request.signal_root,
            feature_root=request.feature_root,
            price_fixture_path=request.price_fixture_path,
            company_id=request.company_id,
            as_of_time=request.ablation_config.evaluation_slice.as_of_time,
        )
        strategy_specs = build_strategy_specs(
            families=[variant.family for variant in request.ablation_config.strategy_variants],
            clock=self.clock,
            workflow_run_id=ablation_run_id,
        )
        spec_by_id = {spec.strategy_spec_id: spec for spec in strategy_specs}
        for variant in request.ablation_config.strategy_variants:
            strategy_spec = spec_by_id.get(variant.strategy_spec_id)
            if strategy_spec is None:
                raise ValueError(
                    "Strategy variant references an unknown strategy_spec_id: "
                    f"{variant.strategy_spec_id}"
                )
            if strategy_spec.family is not variant.family:
                raise ValueError(
                    "Strategy variant family does not match its referenced spec: "
                    f"{variant.strategy_variant_id}"
                )

        source_snapshots = build_strategy_input_snapshots(
            inputs=strategy_inputs,
            evaluation_slice=request.ablation_config.evaluation_slice,
            ablation_config_id=request.ablation_config.ablation_config_id,
            clock=self.clock,
            workflow_run_id=ablation_run_id,
        )
        for strategy_spec in strategy_specs:
            storage_locations.append(
                self._persist_model(store=store, category="strategy_specs", model=strategy_spec)
            )
        for strategy_variant in request.ablation_config.strategy_variants:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="strategy_variants",
                    model=strategy_variant,
                )
            )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="evaluation_slices",
                model=request.ablation_config.evaluation_slice,
            )
        )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="source_snapshots",
                model=source_snapshots.research_signal_snapshot,
            )
        )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="source_snapshots",
                model=source_snapshots.price_snapshot,
            )
        )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="ablation_configs",
                model=request.ablation_config,
            )
        )

        variant_results = []
        variant_backtest_runs: list[BacktestRun] = []
        child_backtest_responses: list[RunBacktestWorkflowResponse] = []
        child_experiments: list[Experiment] = []
        variant_run_evaluations: list[AblationVariantRunEvaluationInput] = []

        for strategy_variant in request.ablation_config.strategy_variants:
            strategy_spec = spec_by_id[strategy_variant.strategy_spec_id]
            materialized = materialize_variant_signals(
                inputs=strategy_inputs,
                variant=strategy_variant,
                evaluation_slice=request.ablation_config.evaluation_slice,
                source_snapshots=source_snapshots,
                clock=self.clock,
                workflow_run_id=ablation_run_id,
            )
            notes.extend(
                [
                    f"{strategy_variant.variant_name}: {note}"
                    for note in materialized.notes
                ]
            )
            variant_signal_root = output_root / "variant_signals" / strategy_variant.strategy_variant_id
            for signal in materialized.signals:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=signal.strategy_variant_signal_id,
                        category=f"variant_signals/{strategy_variant.strategy_variant_id}/signals",
                        model=signal,
                        source_reference_ids=signal.provenance.source_reference_ids,
                    )
                )

            variant_response = self.run_backtest_workflow(
                RunBacktestWorkflowRequest(
                    signal_root=variant_signal_root,
                    signal_arbitration_root=request.signal_arbitration_root,
                    feature_root=request.feature_root,
                    price_fixture_path=request.price_fixture_path,
                    loaded_inputs=build_variant_backtest_inputs(
                        strategy_inputs=strategy_inputs,
                        variant_signals=materialized.signals,
                        variant_signal_root=variant_signal_root,
                    ),
                    output_root=(
                        output_root.parent
                        / "backtesting"
                        / "ablation_runs"
                        / strategy_variant.strategy_variant_id
                    ),
                    company_id=strategy_inputs.company_id,
                    backtest_config=build_variant_backtest_config(
                        shared_backtest_config=request.ablation_config.shared_backtest_config,
                        variant=strategy_variant,
                        strategy_spec=strategy_spec,
                        clock=self.clock,
                        workflow_run_id=ablation_run_id,
                    ),
                    record_experiment=request.ablation_config.record_experiment,
                    experiment_name=f"{request.ablation_config.name}:{strategy_variant.variant_name}",
                    experiment_objective=(
                        "Mechanical Day 9 ablation child run for "
                        f"{strategy_variant.variant_name}."
                    ),
                    experiment_root=experiment_root,
                    requested_by=request.ablation_config.requested_by,
                )
            )
            child_backtest_responses.append(variant_response)
            variant_backtest_runs.append(variant_response.backtest_run)
            storage_locations.extend(variant_response.storage_locations)
            if variant_response.experiment is not None:
                child_experiments.append(variant_response.experiment)
            variant_run_evaluations.append(
                AblationVariantRunEvaluationInput(
                    strategy_variant=strategy_variant,
                    strategy_spec=strategy_spec,
                    variant_signals=materialized.signals,
                    backtest_run=variant_response.backtest_run,
                    performance_summary=variant_response.performance_summary,
                    benchmark_references=variant_response.benchmark_references,
                    dataset_references=variant_response.dataset_references,
                    experiment=variant_response.experiment,
                )
            )
            variant_results.append(
                AblationVariantResult(
                    strategy_variant_id=strategy_variant.strategy_variant_id,
                    family=strategy_variant.family,
                    variant_signal_ids=[
                        signal.strategy_variant_signal_id for signal in materialized.signals
                    ],
                    backtest_run_id=variant_response.backtest_run.backtest_run_id,
                    experiment_id=(
                        variant_response.experiment.experiment_id
                        if variant_response.experiment is not None
                        else None
                    ),
                    performance_summary_id=variant_response.performance_summary.performance_summary_id,
                    benchmark_reference_ids=[
                        benchmark.benchmark_reference_id
                        for benchmark in variant_response.benchmark_references
                    ],
                    dataset_reference_ids=[
                        dataset_reference.dataset_reference_id
                        for dataset_reference in variant_response.dataset_references
                    ],
                    gross_pnl=variant_response.performance_summary.gross_pnl,
                    net_pnl=variant_response.performance_summary.net_pnl,
                    trade_count=variant_response.performance_summary.trade_count,
                    turnover_notional=variant_response.performance_summary.turnover_notional,
                    notes=[
                        f"variant_name={strategy_variant.variant_name}",
                        f"comparison_metric={request.ablation_config.comparison_metric_name}",
                    ],
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day9_ablation_variant_result",
                        upstream_artifact_ids=[
                            strategy_variant.strategy_variant_id,
                            variant_response.backtest_run.backtest_run_id,
                            variant_response.performance_summary.performance_summary_id,
                        ],
                        workflow_run_id=ablation_run_id,
                    ),
                    created_at=self.clock.now(),
                    updated_at=self.clock.now(),
                )
            )

        sorted_results = sort_variant_results(
            results=variant_results,
            comparison_metric_name=request.ablation_config.comparison_metric_name,
        )
        ablation_result = AblationResult(
            ablation_result_id=make_canonical_id(
                "abres",
                request.ablation_config.ablation_config_id,
                request.ablation_config.comparison_metric_name,
            ),
            ablation_config_id=request.ablation_config.ablation_config_id,
            evaluation_slice_id=request.ablation_config.evaluation_slice.evaluation_slice_id,
            variant_results=sorted_results,
            comparison_metric_name=request.ablation_config.comparison_metric_name,
            notes=[
                "Rows are mechanically ordered by the declared comparison metric only.",
                "No ordering implies validation, promotion, or statistical significance.",
            ],
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day9_ablation_result",
                upstream_artifact_ids=[
                    request.ablation_config.ablation_config_id,
                    *[
                        result.backtest_run_id
                        for result in sorted_results
                    ],
                ],
                workflow_run_id=ablation_run_id,
            ),
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        storage_locations.append(
            self._persist_model(store=store, category="ablation_results", model=ablation_result)
        )

        dataset_references = list(
            {
                dataset_reference.dataset_reference_id: dataset_reference
                for response in child_backtest_responses
                for dataset_reference in response.dataset_references
            }.values()
        )
        parent_experiment: Experiment | None = None
        if request.ablation_config.record_experiment and dataset_references:
            experiment_config = build_parent_experiment_config(
                ablation_config=request.ablation_config,
                strategy_specs=strategy_specs,
                clock=self.clock,
                workflow_run_id=ablation_run_id,
            )
            run_context = build_parent_run_context(
                workflow_run_id=ablation_run_id,
                requested_by=request.ablation_config.requested_by,
                artifact_root=output_root,
                as_of_time=request.ablation_config.evaluation_slice.as_of_time,
                clock=self.clock,
            )
            begin_response = ExperimentRegistryService(clock=self.clock).begin_experiment(
                BeginExperimentRequest(
                    name=request.ablation_config.name,
                    objective=(
                        "Mechanical Day 9 comparison across naive, price-only, text-only, "
                        "and combined baseline variants."
                    ),
                    created_by=request.ablation_config.requested_by,
                    experiment_config=experiment_config,
                    run_context=run_context,
                    dataset_references=dataset_references,
                    backtest_run_ids=[
                        response.backtest_run.backtest_run_id
                        for response in child_backtest_responses
                    ],
                    notes=[
                        "Parent experiment aggregates child variant backtests.",
                        "Ordering remains mechanical and non-validated.",
                    ],
                ),
                output_root=experiment_root,
            )
            parent_experiment = begin_response.experiment
            storage_locations.extend(begin_response.storage_locations)

            storage_by_artifact_id = {
                location.artifact_id: location for location in storage_locations
            }
            experiment_artifacts = build_parent_experiment_artifacts(
                experiment=parent_experiment,
                ablation_config=request.ablation_config,
                evaluation_slice=request.ablation_config.evaluation_slice,
                strategy_specs=strategy_specs,
                strategy_variants=request.ablation_config.strategy_variants,
                source_snapshots=source_snapshots,
                ablation_result=ablation_result,
                child_experiments=child_experiments,
                storage_by_artifact_id=storage_by_artifact_id,
                experiment_root=experiment_root,
                clock=self.clock,
                workflow_run_id=ablation_run_id,
            )
            experiment_artifacts.extend(
                self._build_signal_arbitration_experiment_artifacts(
                    experiment=parent_experiment,
                    signal_arbitration_root=request.signal_arbitration_root,
                    company_id=strategy_inputs.company_id,
                    as_of_time=request.ablation_config.evaluation_slice.as_of_time,
                    workflow_run_id=ablation_run_id,
                )
            )
            experiment_metrics = build_parent_experiment_metrics(
                experiment=parent_experiment,
                ablation_result=ablation_result,
                clock=self.clock,
                workflow_run_id=ablation_run_id,
            )
            finalize_response = ExperimentRegistryService(clock=self.clock).finalize_experiment(
                FinalizeExperimentRequest(
                    experiment=parent_experiment,
                    experiment_artifacts=experiment_artifacts,
                    experiment_metrics=experiment_metrics,
                    status=ExperimentStatus.COMPLETED,
                    notes=[
                        f"ablation_result_id={ablation_result.ablation_result_id}",
                        "Parent ablation experiment finalized after child backtests completed.",
                    ],
                ),
                output_root=experiment_root,
            )
            parent_experiment = finalize_response.experiment
            storage_locations.extend(finalize_response.storage_locations)
            notes.append(f"parent_experiment_id={parent_experiment.experiment_id}")

        evaluation_response = EvaluationService(clock=self.clock).evaluate_strategy_ablation(
            EvaluateStrategyAblationRequest(
                ablation_config=request.ablation_config,
                ablation_result=ablation_result,
                strategy_specs=strategy_specs,
                source_snapshots=[
                    source_snapshots.research_signal_snapshot,
                    source_snapshots.price_snapshot,
                ],
                text_signals=strategy_inputs.text_signals,
                features=list(strategy_inputs.features_by_id.values()),
                variant_runs=variant_run_evaluations,
                requested_by=request.ablation_config.requested_by,
            ),
            output_root=evaluation_root,
        )
        storage_locations.extend(evaluation_response.storage_locations)
        notes.extend(evaluation_response.notes)

        audit_response = AuditLoggingService(clock=self.clock).record_event(
            AuditEventRequest(
                event_type="strategy_ablation_completed",
                actor_type="service",
                actor_id="backtesting",
                target_type="ablation_result",
                target_id=ablation_result.ablation_result_id,
                action="completed",
                outcome=AuditOutcome.SUCCESS,
                reason="Deterministic baseline strategy ablation completed.",
                request_id=ablation_run_id,
                related_artifact_ids=[
                    request.ablation_config.ablation_config_id,
                    request.ablation_config.evaluation_slice.evaluation_slice_id,
                    source_snapshots.research_signal_snapshot.data_snapshot_id,
                    source_snapshots.price_snapshot.data_snapshot_id,
                    *[strategy_spec.strategy_spec_id for strategy_spec in strategy_specs],
                    *[
                        strategy_variant.strategy_variant_id
                        for strategy_variant in request.ablation_config.strategy_variants
                    ],
                    *[result.backtest_run_id for result in sorted_results],
                    *[
                        result.experiment_id
                        for result in sorted_results
                        if result.experiment_id is not None
                    ],
                    *[result.performance_summary_id for result in sorted_results],
                    ablation_result.ablation_result_id,
                    *([parent_experiment.experiment_id] if parent_experiment is not None else []),
                ],
                notes=notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)

        evaluation_audit_response = AuditLoggingService(clock=self.clock).record_event(
            AuditEventRequest(
                event_type="evaluation_completed",
                actor_type="service",
                actor_id="evaluation",
                target_type="evaluation_report",
                target_id=evaluation_response.evaluation_report.evaluation_report_id,
                action="completed",
                outcome=AuditOutcome.SUCCESS,
                reason="Deterministic ablation evaluation completed.",
                request_id=ablation_run_id,
                related_artifact_ids=[
                    evaluation_response.evaluation_report.evaluation_report_id,
                    *[
                        metric.evaluation_metric_id
                        for metric in evaluation_response.evaluation_metrics
                    ],
                    *[
                        failure_case.failure_case_id
                        for failure_case in evaluation_response.failure_cases
                    ],
                    *[
                        robustness_check.robustness_check_id
                        for robustness_check in evaluation_response.robustness_checks
                    ],
                    *[
                        coverage_summary.coverage_summary_id
                        for coverage_summary in evaluation_response.coverage_summaries
                    ],
                    *(
                        [evaluation_response.comparison_summary.comparison_summary_id]
                        if evaluation_response.comparison_summary is not None
                        else []
                    ),
                    ablation_result.ablation_result_id,
                ],
                notes=evaluation_response.notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(evaluation_audit_response.storage_location)

        if parent_experiment is not None:
            experiment_audit_response = AuditLoggingService(clock=self.clock).record_event(
                AuditEventRequest(
                    event_type="experiment_completed",
                    actor_type="service",
                    actor_id="experiment_registry",
                    target_type="experiment",
                    target_id=parent_experiment.experiment_id,
                    action="completed",
                    outcome=AuditOutcome.SUCCESS,
                    reason="Parent Day 9 ablation experiment registry records were persisted.",
                    request_id=ablation_run_id,
                    related_artifact_ids=[
                        parent_experiment.experiment_config_id,
                        parent_experiment.run_context_id,
                        *parent_experiment.dataset_reference_ids,
                        *parent_experiment.experiment_artifact_ids,
                        *parent_experiment.experiment_metric_ids,
                    ],
                    notes=notes,
                ),
                output_root=audit_root,
            )
            storage_locations.append(experiment_audit_response.storage_location)

        return RunStrategyAblationWorkflowResponse(
            strategy_specs=strategy_specs,
            strategy_variants=request.ablation_config.strategy_variants,
            ablation_result=ablation_result,
            variant_backtest_runs=variant_backtest_runs,
            experiment=parent_experiment,
            evaluation_report=evaluation_response.evaluation_report,
            evaluation_metrics=evaluation_response.evaluation_metrics,
            failure_cases=evaluation_response.failure_cases,
            robustness_checks=evaluation_response.robustness_checks,
            comparison_summary=evaluation_response.comparison_summary,
            coverage_summaries=evaluation_response.coverage_summaries,
            storage_locations=storage_locations,
            notes=notes,
        )

    def _persist_model(
        self,
        *,
        store: LocalBacktestArtifactStore,
        category: str,
        model: StrictModel,
    ) -> ArtifactStorageLocation:
        """Persist one typed backtesting artifact."""

        artifact_id = _artifact_id(model=model)
        source_reference_ids = cast(_ProvenancedModel, model).provenance.source_reference_ids
        return store.persist_model(
            artifact_id=artifact_id,
            category=category,
            model=model,
            source_reference_ids=source_reference_ids,
        )

    def _build_dataset_registry_records(
        self,
        *,
        company_id: str,
        signal_root: Path,
        price_fixture_path: Path,
        snapshots: list[DataSnapshot],
        backtest_config: BacktestConfig,
        workflow_run_id: str,
        snapshot_storage_locations_by_id: dict[str, ArtifactStorageLocation],
    ) -> tuple[
        list[DataSnapshot],
        list[DatasetManifest],
        list[DatasetPartition],
        list[SourceVersion],
        list[DatasetReference],
    ]:
        """Build manifest and dataset-reference records from existing backtest snapshots."""

        manifests: list[DatasetManifest] = []
        partitions: list[DatasetPartition] = []
        source_versions: list[SourceVersion] = []
        dataset_references: list[DatasetReference] = []
        updated_snapshots: list[DataSnapshot] = []
        now = self.clock.now()

        for snapshot in snapshots:
            snapshot_location = snapshot_storage_locations_by_id.get(snapshot.data_snapshot_id)
            storage_uri = (
                snapshot_location.uri
                if snapshot_location is not None
                else (
                    signal_root.resolve().as_uri()
                    if snapshot.dataset_name == "candidate_signals"
                    else price_fixture_path.resolve().as_uri()
                )
            )
            source_family = (
                "candidate_signals"
                if snapshot.dataset_name == "candidate_signals"
                else "synthetic_price_fixture"
            )
            source_version = SourceVersion(
                source_version_id=make_canonical_id(
                    "sver",
                    snapshot.dataset_name,
                    snapshot.dataset_version,
                    company_id,
                ),
                source_family=source_family,
                version_label=snapshot.dataset_version,
                storage_uri=storage_uri,
                event_time_start=snapshot.event_time_start,
                event_time_watermark=snapshot.watermark_time,
                ingestion_cutoff_time=snapshot.ingestion_cutoff_time,
                notes=[
                    f"data_snapshot_id={snapshot.data_snapshot_id}",
                    "Owned by the backtesting workflow and referenced by the experiment registry.",
                ],
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="day8_source_version_from_backtest_snapshot",
                    source_reference_ids=snapshot.provenance.source_reference_ids,
                    upstream_artifact_ids=[snapshot.data_snapshot_id],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=now,
                updated_at=now,
            )
            source_versions.append(source_version)

            partition = DatasetPartition(
                dataset_partition_id=make_canonical_id(
                    "dpart",
                    snapshot.dataset_name,
                    snapshot.dataset_version,
                    company_id,
                ),
                dataset_name=snapshot.dataset_name,
                partition_key=snapshot.partition_key or "company_id",
                partition_value=company_id,
                data_snapshot_id=snapshot.data_snapshot_id,
                date_range_start=(
                    snapshot.event_time_start.date() if snapshot.event_time_start is not None else None
                ),
                date_range_end=(
                    snapshot.watermark_time.date() if snapshot.watermark_time is not None else None
                ),
                event_time_start=snapshot.event_time_start,
                event_time_end=snapshot.watermark_time,
                ingestion_cutoff_time=snapshot.ingestion_cutoff_time,
                row_count=snapshot.row_count,
                source_version_ids=[source_version.source_version_id],
                storage_location_id=(
                    snapshot_location.artifact_storage_location_id
                    if snapshot_location is not None
                    else None
                ),
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="day8_dataset_partition_from_backtest_snapshot",
                    source_reference_ids=snapshot.provenance.source_reference_ids,
                    upstream_artifact_ids=[
                        snapshot.data_snapshot_id,
                        source_version.source_version_id,
                    ],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=now,
                updated_at=now,
            )
            partitions.append(partition)

            manifest = DatasetManifest(
                dataset_manifest_id=make_canonical_id(
                    "dman",
                    snapshot.dataset_name,
                    snapshot.dataset_version,
                    company_id,
                ),
                dataset_name=snapshot.dataset_name,
                dataset_version=snapshot.dataset_version,
                schema_version=snapshot.schema_version,
                data_layer=snapshot.data_layer,
                storage_uri=storage_uri,
                partition_ids=[partition.dataset_partition_id],
                source_families=snapshot.source_families or [source_family],
                source_version_ids=[source_version.source_version_id],
                source_count=snapshot.source_count,
                row_count=snapshot.row_count,
                lineage_notes=[
                    f"data_snapshot_id={snapshot.data_snapshot_id}",
                    "Manifest captures the local backtesting dataset slice for replay.",
                ],
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="day8_dataset_manifest_from_backtest_snapshot",
                    source_reference_ids=snapshot.provenance.source_reference_ids,
                    upstream_artifact_ids=[
                        snapshot.data_snapshot_id,
                        partition.dataset_partition_id,
                        source_version.source_version_id,
                    ],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=now,
                updated_at=now,
            )
            manifests.append(manifest)

            dataset_references.append(
                DatasetReference(
                    dataset_reference_id=make_canonical_id(
                        "dref",
                        snapshot.dataset_name,
                        snapshot.data_snapshot_id,
                        "input",
                    ),
                    dataset_name=snapshot.dataset_name,
                    usage_role=DatasetUsageRole.INPUT,
                    dataset_manifest_id=manifest.dataset_manifest_id,
                    data_snapshot_id=snapshot.data_snapshot_id,
                    data_layer=snapshot.data_layer,
                    information_cutoff_time=snapshot.information_cutoff_time,
                    schema_version=manifest.schema_version,
                    storage_uri=manifest.storage_uri or storage_uri,
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day8_dataset_reference_from_backtest_snapshot",
                        source_reference_ids=snapshot.provenance.source_reference_ids,
                        upstream_artifact_ids=[
                            manifest.dataset_manifest_id,
                            snapshot.data_snapshot_id,
                        ],
                        workflow_run_id=workflow_run_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
            updated_snapshots.append(snapshot)

        return updated_snapshots, manifests, partitions, source_versions, dataset_references

    def _attach_manifest_ids_to_snapshots(
        self,
        *,
        company_id: str,
        snapshots: list[DataSnapshot],
    ) -> list[DataSnapshot]:
        """Attach deterministic dataset-manifest identifiers before snapshot persistence."""

        now = self.clock.now()
        return [
            snapshot.model_copy(
                update={
                    "dataset_manifest_id": make_canonical_id(
                        "dman",
                        snapshot.dataset_name,
                        snapshot.dataset_version,
                        company_id,
                    ),
                    "updated_at": now,
                    "provenance": snapshot.provenance.model_copy(
                        update={"processing_time": now}
                    ),
                }
            )
            for snapshot in snapshots
        ]

    def _build_experiment_config(
        self,
        *,
        backtest_config: BacktestConfig,
        workflow_run_id: str,
    ) -> ExperimentConfig:
        """Flatten a backtest config into a stable experiment configuration record."""

        parameters = self._build_experiment_parameters(
            backtest_config=backtest_config,
            workflow_run_id=workflow_run_id,
        )
        parameter_hash = sha256(
            json.dumps(
                [
                    {
                        "key": parameter.key,
                        "value_repr": parameter.value_repr,
                        "value_type": parameter.value_type.value,
                    }
                    for parameter in parameters
                ],
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        now = self.clock.now()
        return ExperimentConfig(
            experiment_config_id=make_canonical_id(
                "ecfg",
                "backtesting_workflow",
                get_settings().app_version,
                parameter_hash,
            ),
            workflow_name="backtesting_workflow",
            workflow_version=get_settings().app_version,
            parameter_hash=parameter_hash,
            parameters=parameters,
            source_config_artifact_id=backtest_config.backtest_config_id,
            model_reference_ids=[],
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day8_backtest_experiment_config",
                source_reference_ids=backtest_config.provenance.source_reference_ids,
                upstream_artifact_ids=[
                    backtest_config.backtest_config_id,
                    backtest_config.execution_assumption.execution_assumption_id,
                    *[parameter.experiment_parameter_id for parameter in parameters],
                ],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )

    def _build_experiment_parameters(
        self,
        *,
        backtest_config: BacktestConfig,
        workflow_run_id: str,
    ) -> list[ExperimentParameter]:
        """Create stable parameter rows from one backtest configuration."""

        raw_parameters: list[tuple[str, object, ExperimentParameterValueType]] = [
            ("strategy_name", backtest_config.strategy_name, ExperimentParameterValueType.STRING),
            ("signal_family", backtest_config.signal_family, ExperimentParameterValueType.STRING),
            ("ablation_view", backtest_config.ablation_view.value, ExperimentParameterValueType.ENUM),
            ("test_start", backtest_config.test_start.isoformat(), ExperimentParameterValueType.DATE),
            ("test_end", backtest_config.test_end.isoformat(), ExperimentParameterValueType.DATE),
            (
                "decision_frequency",
                backtest_config.decision_frequency,
                ExperimentParameterValueType.STRING,
            ),
            (
                "signal_status_allowlist",
                json.dumps(
                    [status.value for status in backtest_config.signal_status_allowlist],
                    sort_keys=True,
                ),
                ExperimentParameterValueType.ENUM,
            ),
            ("decision_rule", backtest_config.decision_rule, ExperimentParameterValueType.STRING),
            ("exploratory_only", backtest_config.exploratory_only, ExperimentParameterValueType.BOOLEAN),
            ("starting_cash", backtest_config.starting_cash, ExperimentParameterValueType.FLOAT),
            (
                "benchmark_kinds",
                json.dumps([kind.value for kind in backtest_config.benchmark_kinds], sort_keys=True),
                ExperimentParameterValueType.ENUM,
            ),
            (
                "transaction_cost_bps",
                backtest_config.execution_assumption.transaction_cost_bps,
                ExperimentParameterValueType.FLOAT,
            ),
            (
                "slippage_bps",
                backtest_config.execution_assumption.slippage_bps,
                ExperimentParameterValueType.FLOAT,
            ),
            (
                "execution_lag_bars",
                backtest_config.execution_assumption.execution_lag_bars,
                ExperimentParameterValueType.INTEGER,
            ),
            (
                "decision_price_field",
                backtest_config.execution_assumption.decision_price_field,
                ExperimentParameterValueType.STRING,
            ),
            (
                "execution_price_field",
                backtest_config.execution_assumption.execution_price_field,
                ExperimentParameterValueType.STRING,
            ),
        ]
        if backtest_config.execution_assumption.signal_availability_buffer_minutes is not None:
            raw_parameters.append(
                (
                    "signal_availability_buffer_minutes",
                    backtest_config.execution_assumption.signal_availability_buffer_minutes,
                    ExperimentParameterValueType.INTEGER,
                )
            )

        now = self.clock.now()
        parameters: list[ExperimentParameter] = []
        for key, value, value_type in raw_parameters:
            value_repr = _value_repr(value)
            parameters.append(
                ExperimentParameter(
                    experiment_parameter_id=make_canonical_id(
                        "eparam",
                        "backtesting_workflow",
                        key,
                        value_repr,
                    ),
                    key=key,
                    value_repr=value_repr,
                    value_type=value_type,
                    redacted=False,
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day8_backtest_experiment_parameter",
                        source_reference_ids=backtest_config.provenance.source_reference_ids,
                        upstream_artifact_ids=[
                            backtest_config.backtest_config_id,
                            backtest_config.execution_assumption.execution_assumption_id,
                        ],
                        workflow_run_id=workflow_run_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        return parameters

    def _build_run_context(
        self,
        *,
        workflow_run_id: str,
        requested_by: str,
        artifact_root: Path,
        as_of_time: datetime,
    ) -> RunContext:
        """Build the operational run context used by the experiment record."""

        now = self.clock.now()
        settings = get_settings()
        return RunContext(
            run_context_id=make_canonical_id("rctx", "backtesting_workflow", workflow_run_id),
            workflow_name="backtesting_workflow",
            workflow_run_id=workflow_run_id,
            requested_by=requested_by,
            environment=settings.environment,
            artifact_root_uri=artifact_root.resolve().as_uri(),
            as_of_time=as_of_time,
            notes=["Backtesting is the first integrated workflow for the experiment registry."],
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day8_backtest_run_context",
                workflow_run_id=workflow_run_id,
                notes=[f"requested_by={requested_by}"],
            ),
            created_at=now,
            updated_at=now,
        )

    def _build_experiment_artifacts(
        self,
        *,
        experiment: Experiment,
        backtest_run: BacktestRun,
        snapshots: list[DataSnapshot],
        performance_summary: PerformanceSummary,
        benchmark_references: list[BenchmarkReference],
        storage_by_artifact_id: dict[str, ArtifactStorageLocation],
        workflow_run_id: str,
    ) -> list[ExperimentArtifact]:
        """Build artifact registry rows for the backtest outputs and snapshots."""

        now = self.clock.now()
        artifacts: list[ExperimentArtifact] = []
        backtest_artifacts: list[tuple[str, str, ExperimentArtifactRole]] = [
            (backtest_run.backtest_run_id, "BacktestRun", ExperimentArtifactRole.OUTPUT),
            (
                performance_summary.performance_summary_id,
                "PerformanceSummary",
                ExperimentArtifactRole.SUMMARY,
            ),
            *[
                (snapshot.data_snapshot_id, "DataSnapshot", ExperimentArtifactRole.INPUT_SNAPSHOT)
                for snapshot in snapshots
            ],
            *[
                (
                    benchmark.benchmark_reference_id,
                    "BenchmarkReference",
                    ExperimentArtifactRole.BENCHMARK,
                )
                for benchmark in benchmark_references
            ],
        ]
        for artifact_id, artifact_type, artifact_role in backtest_artifacts:
            storage_location = storage_by_artifact_id.get(artifact_id)
            artifacts.append(
                ExperimentArtifact(
                    experiment_artifact_id=make_canonical_id(
                        "eart",
                        experiment.experiment_id,
                        artifact_role.value,
                        artifact_id,
                    ),
                    experiment_id=experiment.experiment_id,
                    artifact_id=artifact_id,
                    artifact_type=artifact_type,
                    artifact_role=artifact_role,
                    artifact_storage_location_id=(
                        storage_location.artifact_storage_location_id
                        if storage_location is not None
                        else None
                    ),
                    uri=(
                        storage_location.uri
                        if storage_location is not None
                        else f"artifact://{artifact_type.lower()}/{artifact_id}"
                    ),
                    produced_at=now,
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day8_experiment_artifact_from_backtest",
                        upstream_artifact_ids=[artifact_id, experiment.experiment_id],
                        workflow_run_id=workflow_run_id,
                        experiment_id=experiment.experiment_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        return artifacts

    def _build_signal_arbitration_experiment_artifacts(
        self,
        *,
        experiment: Experiment,
        signal_arbitration_root: Path | None,
        company_id: str,
        as_of_time: datetime | None,
        workflow_run_id: str,
    ) -> list[ExperimentArtifact]:
        """Build optional experiment-artifact rows for signal arbitration context."""

        if signal_arbitration_root is None or not signal_arbitration_root.exists():
            return []
        bundle, decision = load_latest_signal_bundle(
            signal_arbitration_root=signal_arbitration_root,
            company_id=company_id,
            as_of_time=as_of_time,
        )
        if bundle is None or decision is None:
            return []

        calibrations = [
            calibration
            for calibration in load_signal_arbitration_models(
                root=signal_arbitration_root,
                category="signal_calibrations",
                model_cls=SignalCalibration,
            )
            if calibration.signal_calibration_id in bundle.signal_calibration_ids
        ]
        conflicts = [
            conflict
            for conflict in load_signal_arbitration_models(
                root=signal_arbitration_root,
                category="signal_conflicts",
                model_cls=SignalConflict,
            )
            if conflict.signal_conflict_id in bundle.signal_conflict_ids
        ]
        now = self.clock.now()
        arbitration_artifacts: list[tuple[str, str, ExperimentArtifactRole]] = [
            (bundle.signal_bundle_id, "SignalBundle", ExperimentArtifactRole.INPUT_SNAPSHOT),
            (
                decision.arbitration_decision_id,
                "ArbitrationDecision",
                ExperimentArtifactRole.SUMMARY,
            ),
            *[
                (
                    calibration.signal_calibration_id,
                    "SignalCalibration",
                    ExperimentArtifactRole.DIAGNOSTIC,
                )
                for calibration in calibrations
            ],
            *[
                (
                    conflict.signal_conflict_id,
                    "SignalConflict",
                    ExperimentArtifactRole.DIAGNOSTIC,
                )
                for conflict in conflicts
            ],
        ]
        return [
            ExperimentArtifact(
                experiment_artifact_id=make_canonical_id(
                    "eart",
                    experiment.experiment_id,
                    artifact_role.value,
                    artifact_id,
                ),
                experiment_id=experiment.experiment_id,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                artifact_role=artifact_role,
                artifact_storage_location_id=None,
                uri=(signal_arbitration_root / _category_for_artifact_type(artifact_type) / f"{artifact_id}.json").resolve().as_uri(),
                produced_at=now,
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="day19_experiment_artifact_from_signal_arbitration",
                    upstream_artifact_ids=[artifact_id, experiment.experiment_id],
                    workflow_run_id=workflow_run_id,
                    experiment_id=experiment.experiment_id,
                ),
                created_at=now,
                updated_at=now,
            )
            for artifact_id, artifact_type, artifact_role in arbitration_artifacts
        ]

    def _build_experiment_metrics(
        self,
        *,
        experiment: Experiment,
        performance_summary: PerformanceSummary,
        benchmark_references: list[BenchmarkReference],
        workflow_run_id: str,
    ) -> list[ExperimentMetric]:
        """Build numeric experiment metrics from the mechanical backtest summary."""

        now = self.clock.now()
        metrics: list[ExperimentMetric] = []
        summary_metrics: list[tuple[str, float, str | None]] = [
            ("gross_pnl", performance_summary.gross_pnl, "usd"),
            ("net_pnl", performance_summary.net_pnl, "usd"),
            ("trade_count", float(performance_summary.trade_count), "count"),
            ("turnover_notional", performance_summary.turnover_notional, "usd"),
        ]
        for metric_name, numeric_value, unit in summary_metrics:
            metrics.append(
                ExperimentMetric(
                    experiment_metric_id=make_canonical_id(
                        "emetric",
                        experiment.experiment_id,
                        metric_name,
                    ),
                    experiment_id=experiment.experiment_id,
                    metric_name=metric_name,
                    numeric_value=numeric_value,
                    unit=unit,
                    source_artifact_id=performance_summary.performance_summary_id,
                    recorded_at=now,
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day8_experiment_metric_from_backtest_summary",
                        upstream_artifact_ids=[
                            performance_summary.performance_summary_id,
                            experiment.experiment_id,
                        ],
                        workflow_run_id=workflow_run_id,
                        experiment_id=experiment.experiment_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        for benchmark in benchmark_references:
            metrics.append(
                ExperimentMetric(
                    experiment_metric_id=make_canonical_id(
                        "emetric",
                        experiment.experiment_id,
                        benchmark.benchmark_reference_id,
                        "simple_return",
                    ),
                    experiment_id=experiment.experiment_id,
                    metric_name=f"benchmark_simple_return:{benchmark.benchmark_kind.value}",
                    numeric_value=benchmark.simple_return,
                    unit="ratio",
                    source_artifact_id=benchmark.benchmark_reference_id,
                    recorded_at=now,
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day8_experiment_metric_from_benchmark",
                        upstream_artifact_ids=[
                            benchmark.benchmark_reference_id,
                            experiment.experiment_id,
                        ],
                        workflow_run_id=workflow_run_id,
                        experiment_id=experiment.experiment_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        return metrics


class _ProvenancedModel(Protocol):
    provenance: ProvenanceRecord


def _artifact_id(*, model: StrictModel) -> str:
    """Resolve the canonical identifier field for a strict model."""

    if hasattr(model, "data_snapshot_id"):
        return cast(str, model.data_snapshot_id)
    for field_name in type(model).model_fields:
        if field_name.endswith("_id"):
            value = getattr(model, field_name, None)
            if isinstance(value, str):
                return value
    raise ValueError(f"Could not resolve artifact ID for model type `{type(model).__name__}`.")


def _value_repr(value: object) -> str:
    """Return a stable string representation for recorded experiment parameters."""

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _category_for_artifact_type(artifact_type: str) -> str:
    """Return the persisted category directory for one arbitration artifact type."""

    return {
        "SignalBundle": "signal_bundles",
        "ArbitrationDecision": "arbitration_decisions",
        "SignalCalibration": "signal_calibrations",
        "SignalConflict": "signal_conflicts",
    }[artifact_type]
