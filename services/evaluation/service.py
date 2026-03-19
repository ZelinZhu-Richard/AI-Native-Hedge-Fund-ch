from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AblationConfig,
    AblationResult,
    ArtifactStorageLocation,
    ComparisonSummary,
    CoverageSummary,
    DataSnapshot,
    EvaluationMetric,
    EvaluationReport,
    FailureCase,
    Feature,
    RobustnessCheck,
    Signal,
    StrategySpec,
    StrictModel,
)
from libraries.utils import make_canonical_id
from services.evaluation.checks import (
    AblationVariantRunEvaluationInput,
    EvaluationArtifacts,
    build_evaluation_report,
    evaluate_backtest_artifact_completeness,
    evaluate_feature_lineage_completeness,
    evaluate_provenance_completeness,
    evaluate_signal_generation_validity,
    evaluate_strategy_comparison_output,
    robustness_incomplete_extraction_artifact,
    robustness_invalid_strategy_config,
    robustness_missing_data_sensitivity,
    robustness_source_inconsistency,
    robustness_timestamp_anomaly,
)
from services.evaluation.storage import LocalEvaluationArtifactStore


class EvaluateStrategyAblationRequest(StrictModel):
    """Structured input bundle for Day 10 ablation evaluation."""

    ablation_config: AblationConfig = Field(description="Ablation configuration under evaluation.")
    ablation_result: AblationResult = Field(description="Ablation result under evaluation.")
    strategy_specs: list[StrategySpec] = Field(
        default_factory=list,
        description="Strategy specifications used by the ablation run.",
    )
    source_snapshots: list[DataSnapshot] = Field(
        default_factory=list,
        description="Shared snapshots used by the ablation run.",
    )
    text_signals: list[Signal] = Field(
        default_factory=list,
        description="Source research signals used by text-aware variants.",
    )
    features: list[Feature] = Field(
        default_factory=list,
        description="Source features used by the Day 5 text signal slice.",
    )
    variant_runs: list[AblationVariantRunEvaluationInput] = Field(
        default_factory=list,
        description="Child ablation backtest runs and comparable signals.",
    )
    requested_by: str = Field(description="Requester or workflow owner.")


class EvaluateStrategyAblationResponse(StrictModel):
    """Persisted Day 10 evaluation outputs for one ablation run."""

    evaluation_report: EvaluationReport = Field(description="Primary evaluation report artifact.")
    evaluation_metrics: list[EvaluationMetric] = Field(
        default_factory=list,
        description="Evaluation metrics emitted for the ablation run.",
    )
    failure_cases: list[FailureCase] = Field(
        default_factory=list,
        description="Failure cases recorded by the evaluation layer.",
    )
    robustness_checks: list[RobustnessCheck] = Field(
        default_factory=list,
        description="Robustness checks recorded by the evaluation layer.",
    )
    comparison_summary: ComparisonSummary | None = Field(
        default=None,
        description="Optional comparison summary emitted for the ablation run.",
    )
    coverage_summaries: list[CoverageSummary] = Field(
        default_factory=list,
        description="Coverage summaries emitted by the evaluation layer.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Persisted evaluation artifact locations.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes attached to the evaluation run.",
    )


class EvaluationService(BaseService):
    """Evaluate structural quality, failures, and robustness of downstream workflows."""

    capability_name = "evaluation"
    capability_description = (
        "Evaluates structural quality, provenance completeness, failures, and robustness."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=[
                "Hypothesis",
                "Feature",
                "Signal",
                "BacktestRun",
                "AblationResult",
                "PortfolioProposal",
            ],
            produces=[
                "EvaluationReport",
                "EvaluationMetric",
                "FailureCase",
                "RobustnessCheck",
                "CoverageSummary",
                "ComparisonSummary",
            ],
            api_routes=[],
        )

    def evaluate_strategy_ablation(
        self,
        request: EvaluateStrategyAblationRequest,
        *,
        output_root: Path | None = None,
    ) -> EvaluateStrategyAblationResponse:
        """Evaluate one completed Day 9 ablation run structurally and honestly."""

        evaluation_run_id = make_canonical_id(
            "evalrun",
            request.ablation_result.ablation_result_id,
            request.requested_by,
        )
        evaluation_report_id = make_canonical_id(
            "evrep",
            request.ablation_result.ablation_result_id,
            "day10",
        )
        store = LocalEvaluationArtifactStore(
            root=output_root or (get_settings().resolved_artifact_root / "evaluation"),
            clock=self.clock,
        )
        notes = [
            "Day 10 evaluation remains deterministic and structural.",
            "No evaluation output implies validated edge or promotion.",
            f"requested_by={request.requested_by}",
        ]
        artifacts = self._evaluate_ablation_bundle(
            evaluation_report_id=evaluation_report_id,
            request=request,
            workflow_run_id=evaluation_run_id,
        )
        artifacts.notes.extend(notes)
        evaluation_report = build_evaluation_report(
            evaluation_report_id=evaluation_report_id,
            target_type="ablation_result",
            target_id=request.ablation_result.ablation_result_id,
            artifacts=artifacts,
            clock=self.clock,
            workflow_run_id=evaluation_run_id,
        )

        storage_locations: list[ArtifactStorageLocation] = []
        for metric in artifacts.metrics:
            storage_locations.append(
                self._persist_model(store=store, category="metrics", model=metric)
            )
        for failure_case in artifacts.failure_cases:
            storage_locations.append(
                self._persist_model(store=store, category="failure_cases", model=failure_case)
            )
        for robustness_check in artifacts.robustness_checks:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="robustness_checks",
                    model=robustness_check,
                )
            )
        for coverage_summary in artifacts.coverage_summaries:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="coverage_summaries",
                    model=coverage_summary,
                )
            )
        if artifacts.comparison_summary is not None:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="comparison_summaries",
                    model=artifacts.comparison_summary,
                )
            )
        storage_locations.append(
            self._persist_model(store=store, category="reports", model=evaluation_report)
        )

        return EvaluateStrategyAblationResponse(
            evaluation_report=evaluation_report,
            evaluation_metrics=artifacts.metrics,
            failure_cases=artifacts.failure_cases,
            robustness_checks=artifacts.robustness_checks,
            comparison_summary=artifacts.comparison_summary,
            coverage_summaries=artifacts.coverage_summaries,
            storage_locations=storage_locations,
            notes=artifacts.notes,
        )

    def _evaluate_ablation_bundle(
        self,
        *,
        evaluation_report_id: str,
        request: EvaluateStrategyAblationRequest,
        workflow_run_id: str,
    ) -> EvaluationArtifacts:
        """Run the concrete Day 10 ablation evaluation checks."""

        artifacts = EvaluationArtifacts()
        flattened_variant_signals = [
            signal
            for variant_run in request.variant_runs
            for signal in variant_run.variant_signals
        ]
        snapshots_by_id = {
            snapshot.data_snapshot_id: snapshot for snapshot in request.source_snapshots
        }
        known_signal_ids = {signal.signal_id for signal in request.text_signals}
        features_by_id = {feature.feature_id: feature for feature in request.features}

        provenance_artifacts: list[StrictModel] = [
            request.ablation_config,
            request.ablation_result,
            *request.strategy_specs,
            *request.source_snapshots,
            *request.text_signals,
            *request.features,
            *flattened_variant_signals,
            *[variant_run.backtest_run for variant_run in request.variant_runs],
            *[variant_run.performance_summary for variant_run in request.variant_runs],
            *[
                benchmark_reference
                for variant_run in request.variant_runs
                for benchmark_reference in variant_run.benchmark_references
            ],
            *[
                dataset_reference
                for variant_run in request.variant_runs
                for dataset_reference in variant_run.dataset_references
            ],
            *[
                variant_run.experiment
                for variant_run in request.variant_runs
                if variant_run.experiment is not None
            ],
        ]
        artifacts.extend(
            evaluate_provenance_completeness(
                evaluation_report_id=evaluation_report_id,
                target_type="ablation_result",
                target_id=request.ablation_result.ablation_result_id,
                artifacts=provenance_artifacts,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
        )
        artifacts.extend(
            evaluate_feature_lineage_completeness(
                evaluation_report_id=evaluation_report_id,
                target_type="feature_slice",
                target_id=request.ablation_result.ablation_result_id,
                features=request.features,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
        )
        artifacts.extend(
            evaluate_signal_generation_validity(
                evaluation_report_id=evaluation_report_id,
                target_type="research_signal_slice",
                target_id=request.ablation_result.ablation_result_id,
                signals=request.text_signals,
                features_by_id=features_by_id,
                known_signal_ids=known_signal_ids,
                snapshots_by_id=snapshots_by_id,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
        )
        artifacts.extend(
            evaluate_signal_generation_validity(
                evaluation_report_id=evaluation_report_id,
                target_type="strategy_variant_signal_slice",
                target_id=request.ablation_result.ablation_result_id,
                signals=flattened_variant_signals,
                features_by_id=features_by_id,
                known_signal_ids=known_signal_ids,
                snapshots_by_id=snapshots_by_id,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
        )
        artifacts.extend(
            evaluate_backtest_artifact_completeness(
                evaluation_report_id=evaluation_report_id,
                target_type="backtest_run_slice",
                target_id=request.ablation_result.ablation_result_id,
                variant_runs=request.variant_runs,
                record_experiment_expected=request.ablation_config.record_experiment,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
        )
        artifacts.extend(
            evaluate_strategy_comparison_output(
                evaluation_report_id=evaluation_report_id,
                ablation_config=request.ablation_config,
                ablation_result=request.ablation_result,
                strategy_specs=request.strategy_specs,
                strategy_variants=request.ablation_config.strategy_variants,
                variant_runs=request.variant_runs,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
        )
        evaluation_slice_start = datetime.combine(
            request.ablation_config.evaluation_slice.test_start,
            datetime.min.time(),
            tzinfo=self.clock.now().tzinfo,
        )
        evaluation_slice_end = datetime.combine(
            request.ablation_config.evaluation_slice.test_end,
            datetime.max.time(),
            tzinfo=self.clock.now().tzinfo,
        )
        artifacts.robustness_checks.extend(
            [
                robustness_missing_data_sensitivity(
                    evaluation_report_id=evaluation_report_id,
                    target_id=request.ablation_result.ablation_result_id,
                    variant_runs=request.variant_runs,
                    clock=self.clock,
                    workflow_run_id=workflow_run_id,
                ),
                robustness_timestamp_anomaly(
                    evaluation_report_id=evaluation_report_id,
                    target_id=request.ablation_result.ablation_result_id,
                    evaluation_slice_start=evaluation_slice_start,
                    evaluation_slice_end=evaluation_slice_end,
                    source_snapshots=request.source_snapshots,
                    text_signals=request.text_signals,
                    variant_runs=request.variant_runs,
                    clock=self.clock,
                    workflow_run_id=workflow_run_id,
                ),
                robustness_source_inconsistency(
                    evaluation_report_id=evaluation_report_id,
                    target_id=request.ablation_result.ablation_result_id,
                    expected_company_id=request.ablation_config.evaluation_slice.company_id,
                    source_snapshots=request.source_snapshots,
                    text_signals=request.text_signals,
                    features=request.features,
                    variant_runs=request.variant_runs,
                    clock=self.clock,
                    workflow_run_id=workflow_run_id,
                ),
                robustness_incomplete_extraction_artifact(
                    evaluation_report_id=evaluation_report_id,
                    target_id=request.ablation_result.ablation_result_id,
                    text_signals=request.text_signals,
                    features=request.features,
                    clock=self.clock,
                    workflow_run_id=workflow_run_id,
                ),
                robustness_invalid_strategy_config(
                    evaluation_report_id=evaluation_report_id,
                    ablation_config=request.ablation_config,
                    strategy_specs=request.strategy_specs,
                    clock=self.clock,
                    workflow_run_id=workflow_run_id,
                ),
            ]
        )
        return artifacts

    def _persist_model(
        self,
        *,
        store: LocalEvaluationArtifactStore,
        category: str,
        model: StrictModel,
    ) -> ArtifactStorageLocation:
        """Persist one evaluation artifact."""

        artifact_id = self._artifact_id(model)
        provenance = getattr(model, "provenance", None)
        source_reference_ids = provenance.source_reference_ids if provenance is not None else []
        return store.persist_model(
            artifact_id=artifact_id,
            category=category,
            model=model,
            source_reference_ids=source_reference_ids,
        )

    def _artifact_id(self, model: StrictModel) -> str:
        field_names_by_model = {
            "EvaluationReport": ("evaluation_report_id",),
            "EvaluationMetric": ("evaluation_metric_id",),
            "FailureCase": ("failure_case_id",),
            "RobustnessCheck": ("robustness_check_id",),
            "ComparisonSummary": ("comparison_summary_id",),
            "CoverageSummary": ("coverage_summary_id",),
        }
        field_names = field_names_by_model.get(
            type(model).__name__,
            (
                "evaluation_metric_id",
                "failure_case_id",
                "robustness_check_id",
                "comparison_summary_id",
                "coverage_summary_id",
                "evaluation_report_id",
            ),
        )
        for field_name in field_names:
            value = getattr(model, field_name, None)
            if value:
                return str(value)
        raise ValueError(f"Unable to resolve artifact ID for {type(model).__name__}.")
