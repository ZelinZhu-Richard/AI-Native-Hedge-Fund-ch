from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol, cast

from pydantic import Field

from libraries.config import get_settings
from libraries.core import build_provenance
from libraries.schemas import (
    AblationConfig,
    AblationResult,
    AblationVariantResult,
    AblationView,
    ArtifactStorageLocation,
    BacktestConfig,
    DataLayer,
    DataSnapshot,
    DerivedArtifactValidationStatus,
    EvaluationSlice,
    Experiment,
    ExperimentArtifact,
    ExperimentArtifactRole,
    ExperimentConfig,
    ExperimentMetric,
    ExperimentParameter,
    ExperimentParameterValueType,
    Feature,
    ResearchStance,
    RunContext,
    Signal,
    SignalStatus,
    StrategyFamily,
    StrategySpec,
    StrategyVariant,
    StrategyVariantSignal,
    StrictModel,
)
from libraries.time import Clock, ensure_utc
from libraries.utils import make_canonical_id
from services.backtesting.loaders import (
    LoadedBacktestInputs,
    SyntheticDailyPriceBar,
    SyntheticPriceFixture,
    load_backtest_inputs,
)


class LoadedStrategyInputs(StrictModel):
    """Shared Day 9 inputs used by all strategy-variant executors."""

    company_id: str = Field(description="Covered company identifier.")
    signal_root: Path = Field(description="Root path for persisted research signal artifacts.")
    feature_root: Path = Field(description="Root path for persisted feature artifacts.")
    price_fixture_path: Path = Field(description="Path to the shared synthetic price fixture.")
    text_signals: list[Signal] = Field(
        default_factory=list,
        description="Research candidate signals available to text and combined variants.",
    )
    research_signals_by_id: dict[str, Signal] = Field(
        default_factory=dict,
        description="Research signals keyed by signal identifier for lineage reuse.",
    )
    features_by_id: dict[str, Feature] = Field(
        default_factory=dict,
        description="Feature artifacts keyed by feature identifier.",
    )
    price_fixture: SyntheticPriceFixture = Field(description="Shared synthetic price fixture.")


class MaterializedVariantSignals(StrictModel):
    """Comparable signals emitted for one strategy variant."""

    signals: list[StrategyVariantSignal] = Field(
        default_factory=list,
        description="Comparable signals emitted by the variant.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes about the variant materialization.",
    )


class StrategyInputSnapshots(StrictModel):
    """Shared snapshot metadata for the ablation input boundary."""

    research_signal_snapshot: DataSnapshot = Field(
        description="Snapshot describing the upstream research signal slice."
    )
    price_snapshot: DataSnapshot = Field(
        description="Snapshot describing the shared synthetic price slice."
    )


class StrategyVariantExecutor(Protocol):
    """Protocol implemented by deterministic Day 9 strategy variants."""

    def materialize_signals(
        self,
        *,
        inputs: LoadedStrategyInputs,
        variant: StrategyVariant,
        evaluation_slice: EvaluationSlice,
        source_snapshots: StrategyInputSnapshots,
        clock: Clock,
        workflow_run_id: str,
    ) -> MaterializedVariantSignals:
        """Materialize comparable signals for one strategy variant."""


def load_strategy_inputs(
    *,
    signal_root: Path,
    feature_root: Path,
    price_fixture_path: Path,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
) -> LoadedStrategyInputs:
    """Load shared Day 9 strategy inputs from persisted artifacts."""

    loaded = load_backtest_inputs(
        signal_root=signal_root,
        feature_root=feature_root,
        price_fixture_path=price_fixture_path,
        company_id=company_id,
    )
    text_signals = list(loaded.research_signals_by_id.values())
    if as_of_time is not None:
        text_signals = [
            signal
            for signal in text_signals
            if signal.created_at <= as_of_time and signal.effective_at <= as_of_time
        ]

    return LoadedStrategyInputs(
        company_id=loaded.company_id,
        signal_root=loaded.signal_root,
        feature_root=loaded.feature_root,
        price_fixture_path=loaded.price_fixture_path,
        text_signals=text_signals,
        research_signals_by_id=loaded.research_signals_by_id,
        features_by_id=loaded.features_by_id,
        price_fixture=loaded.price_fixture,
    )


def build_strategy_specs(
    *,
    families: list[StrategyFamily],
    clock: Clock,
    workflow_run_id: str,
) -> list[StrategySpec]:
    """Build stable strategy specifications for the requested families."""

    now = clock.now()
    specs: list[StrategySpec] = []
    for family in list(dict.fromkeys(families)):
        signal_family, description, required_inputs, decision_rule_name = _spec_definition(family)
        specs.append(
            StrategySpec(
                strategy_spec_id=make_canonical_id("sspec", family.value, signal_family),
                name=family.value,
                family=family,
                description=description,
                signal_family=signal_family,
                required_inputs=required_inputs,
                decision_rule_name=decision_rule_name,
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day9_strategy_spec",
                    workflow_run_id=workflow_run_id,
                    notes=[f"family={family.value}"],
                ),
                created_at=now,
                updated_at=now,
            )
        )
    return specs


def build_default_strategy_variants(
    *,
    strategy_specs: list[StrategySpec],
    clock: Clock,
    workflow_run_id: str,
) -> list[StrategyVariant]:
    """Build the default Day 9 strategy variants from their family specs."""

    spec_by_family = {spec.family: spec for spec in strategy_specs}
    now = clock.now()
    variants: list[StrategyVariant] = []
    for family in [
        StrategyFamily.NAIVE_BASELINE,
        StrategyFamily.PRICE_ONLY_BASELINE,
        StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
        StrategyFamily.COMBINED_BASELINE,
    ]:
        spec = spec_by_family[family]
        variants.append(
            StrategyVariant(
                strategy_variant_id=make_canonical_id("svar", family.value, spec.strategy_spec_id),
                strategy_spec_id=spec.strategy_spec_id,
                variant_name=family.value,
                family=family,
                parameters=_default_variant_parameters(
                    family=family,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                ),
                notes=["Day 9 strategy variants are deterministic mechanical baselines only."],
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day9_strategy_variant",
                    upstream_artifact_ids=[spec.strategy_spec_id],
                    workflow_run_id=workflow_run_id,
                    notes=[f"family={family.value}"],
                ),
                created_at=now,
                updated_at=now,
            )
        )
    return variants


def build_strategy_input_snapshots(
    *,
    inputs: LoadedStrategyInputs,
    evaluation_slice: EvaluationSlice,
    ablation_config_id: str,
    clock: Clock,
    workflow_run_id: str,
) -> StrategyInputSnapshots:
    """Build shared snapshot metadata for the strategy input boundary."""

    now = clock.now()
    slice_bars = _bars_in_slice(inputs=inputs, evaluation_slice=evaluation_slice)
    slice_signals = _text_signals_in_slice(inputs=inputs, evaluation_slice=evaluation_slice)

    signal_event_time_start = min((signal.effective_at for signal in slice_signals), default=None)
    signal_watermark = max((signal.effective_at for signal in slice_signals), default=None)
    signal_ingestion_cutoff = max((signal.created_at for signal in slice_signals), default=None)
    signal_information_cutoff = (
        evaluation_slice.as_of_time or signal_watermark or max(now, slice_bars[-1].timestamp_dt)
    )
    signal_snapshot = DataSnapshot(
        data_snapshot_id=make_canonical_id(
            "snap",
            inputs.company_id,
            "ablation_source_signals",
            ablation_config_id,
        ),
        dataset_name="candidate_signals",
        dataset_version=ablation_config_id,
        dataset_manifest_id=None,
        data_layer=DataLayer.DERIVED,
        snapshot_time=max(now, signal_information_cutoff),
        event_time_start=signal_event_time_start,
        watermark_time=signal_watermark,
        ingestion_cutoff_time=signal_ingestion_cutoff,
        information_cutoff_time=signal_information_cutoff,
        storage_uri=inputs.signal_root.resolve().as_uri(),
        row_count=len(slice_signals),
        schema_version="day9_ablation",
        partition_key=inputs.company_id,
        source_count=len(
            {
                source_reference_id
                for signal in slice_signals
                for source_reference_id in signal.provenance.source_reference_ids
            }
        ),
        completeness_ratio=1.0 if slice_signals else 0.0,
        source_families=["candidate_signals"],
        created_by_process="day9_ablation_source_signal_snapshot",
        provenance=build_provenance(
            clock=clock,
            transformation_name="day9_ablation_source_signal_snapshot",
            source_reference_ids=[
                source_reference_id
                for signal in slice_signals
                for source_reference_id in signal.provenance.source_reference_ids
            ],
            upstream_artifact_ids=[signal.signal_id for signal in slice_signals],
            workflow_run_id=workflow_run_id,
            notes=["Snapshot captures the upstream research-signal slice for ablation comparison."],
        ),
        created_at=now,
        updated_at=now,
    )

    first_bar = slice_bars[0].timestamp_dt
    last_bar = slice_bars[-1].timestamp_dt
    price_snapshot = DataSnapshot(
        data_snapshot_id=make_canonical_id(
            "snap",
            inputs.company_id,
            "ablation_source_prices",
            ablation_config_id,
        ),
        dataset_name="synthetic_daily_prices",
        dataset_version=ablation_config_id,
        dataset_manifest_id=None,
        data_layer=DataLayer.NORMALIZED,
        snapshot_time=max(now, last_bar),
        event_time_start=first_bar,
        watermark_time=last_bar,
        ingestion_cutoff_time=None,
        information_cutoff_time=last_bar,
        storage_uri=inputs.price_fixture_path.resolve().as_uri(),
        row_count=len(slice_bars),
        schema_version="day9_ablation",
        partition_key=inputs.company_id,
        source_count=1,
        completeness_ratio=1.0,
        source_families=["synthetic_price_fixture"],
        created_by_process="day9_ablation_source_price_snapshot",
        provenance=build_provenance(
            clock=clock,
            transformation_name="day9_ablation_source_price_snapshot",
            workflow_run_id=workflow_run_id,
            notes=["Synthetic price fixture remains mechanical test infrastructure only."],
        ),
        created_at=now,
        updated_at=now,
    )

    return StrategyInputSnapshots(
        research_signal_snapshot=signal_snapshot,
        price_snapshot=price_snapshot,
    )


def materialize_variant_signals(
    *,
    inputs: LoadedStrategyInputs,
    variant: StrategyVariant,
    evaluation_slice: EvaluationSlice,
    source_snapshots: StrategyInputSnapshots,
    clock: Clock,
    workflow_run_id: str,
) -> MaterializedVariantSignals:
    """Materialize comparable signals for one configured strategy variant."""

    executors: dict[StrategyFamily, StrategyVariantExecutor] = {
        StrategyFamily.NAIVE_BASELINE: _NaiveBaselineExecutor(),
        StrategyFamily.PRICE_ONLY_BASELINE: _PriceOnlyMomentumExecutor(),
        StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE: _TextOnlyCandidateExecutor(),
        StrategyFamily.COMBINED_BASELINE: _CombinedBaselineExecutor(),
    }
    executor = executors[variant.family]
    return executor.materialize_signals(
        inputs=inputs,
        variant=variant,
        evaluation_slice=evaluation_slice,
        source_snapshots=source_snapshots,
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def build_variant_backtest_config(
    *,
    shared_backtest_config: BacktestConfig,
    variant: StrategyVariant,
    strategy_spec: StrategySpec,
    clock: Clock,
    workflow_run_id: str,
) -> BacktestConfig:
    """Build the child backtest config used for one strategy variant."""

    now = clock.now()
    return shared_backtest_config.model_copy(
        update={
            "backtest_config_id": make_canonical_id(
                "btcfg",
                shared_backtest_config.backtest_config_id,
                variant.strategy_variant_id,
            ),
            "strategy_name": variant.variant_name,
            "signal_family": strategy_spec.signal_family,
            "ablation_view": _ablation_view_for_family(variant.family),
            "updated_at": now,
            "provenance": build_provenance(
                clock=clock,
                transformation_name="day9_variant_backtest_config",
                source_reference_ids=shared_backtest_config.provenance.source_reference_ids,
                upstream_artifact_ids=[
                    shared_backtest_config.backtest_config_id,
                    variant.strategy_variant_id,
                    strategy_spec.strategy_spec_id,
                ],
                workflow_run_id=workflow_run_id,
                notes=[f"variant_name={variant.variant_name}"],
            ),
        }
    )


def build_variant_backtest_inputs(
    *,
    strategy_inputs: LoadedStrategyInputs,
    variant_signals: list[StrategyVariantSignal],
    variant_signal_root: Path,
) -> LoadedBacktestInputs:
    """Build generic comparable backtest inputs for one strategy variant."""

    return LoadedBacktestInputs(
        company_id=strategy_inputs.company_id,
        signal_root=variant_signal_root,
        feature_root=strategy_inputs.feature_root,
        price_fixture_path=strategy_inputs.price_fixture_path,
        signals=cast(list[Signal | StrategyVariantSignal], list(variant_signals)),
        research_signals_by_id=strategy_inputs.research_signals_by_id,
        features_by_id=strategy_inputs.features_by_id,
        price_fixture=strategy_inputs.price_fixture,
    )


def sort_variant_results(
    *,
    results: list[AblationVariantResult],
    comparison_metric_name: str,
) -> list[AblationVariantResult]:
    """Return mechanically ordered comparison rows for the ablation result."""

    return sorted(
        results,
        key=lambda result: (
            -_comparison_metric_value(result=result, metric_name=comparison_metric_name),
            result.strategy_variant_id,
        ),
    )


def build_parent_experiment_config(
    *,
    ablation_config: AblationConfig,
    strategy_specs: list[StrategySpec],
    clock: Clock,
    workflow_run_id: str,
) -> ExperimentConfig:
    """Build the parent experiment config for the Day 9 ablation harness."""

    parameters = _ablation_experiment_parameters(
        ablation_config=ablation_config,
        strategy_specs=strategy_specs,
        clock=clock,
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
    now = clock.now()
    return ExperimentConfig(
        experiment_config_id=make_canonical_id(
            "ecfg",
            "strategy_ablation_workflow",
            get_settings().app_version,
            parameter_hash,
        ),
        workflow_name="strategy_ablation_workflow",
        workflow_version=get_settings().app_version,
        parameter_hash=parameter_hash,
        parameters=parameters,
        source_config_artifact_id=ablation_config.ablation_config_id,
        model_reference_ids=[],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day9_ablation_experiment_config",
            upstream_artifact_ids=[
                ablation_config.ablation_config_id,
                *[parameter.experiment_parameter_id for parameter in parameters],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_parent_run_context(
    *,
    workflow_run_id: str,
    requested_by: str,
    artifact_root: Path,
    as_of_time: datetime | None,
    clock: Clock,
) -> RunContext:
    """Build the parent ablation run context for experiment recording."""

    now = clock.now()
    settings = get_settings()
    return RunContext(
        run_context_id=make_canonical_id("rctx", "strategy_ablation_workflow", workflow_run_id),
        workflow_name="strategy_ablation_workflow",
        workflow_run_id=workflow_run_id,
        requested_by=requested_by,
        environment=settings.environment,
        artifact_root_uri=artifact_root.resolve().as_uri(),
        as_of_time=as_of_time,
        notes=["Parent ablation experiment aggregates multiple child backtest experiments."],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day9_ablation_run_context",
            workflow_run_id=workflow_run_id,
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=now,
        updated_at=now,
    )


def build_parent_experiment_artifacts(
    *,
    experiment: Experiment,
    ablation_config: AblationConfig,
    evaluation_slice: EvaluationSlice,
    strategy_specs: list[StrategySpec],
    strategy_variants: list[StrategyVariant],
    source_snapshots: StrategyInputSnapshots,
    ablation_result: AblationResult,
    child_experiments: list[Experiment],
    storage_by_artifact_id: dict[str, ArtifactStorageLocation],
    experiment_root: Path,
    clock: Clock,
    workflow_run_id: str,
) -> list[ExperimentArtifact]:
    """Build parent experiment-artifact records for the ablation harness."""

    now = clock.now()
    artifacts: list[ExperimentArtifact] = []
    for artifact_id, artifact_type, artifact_role in [
        (ablation_config.ablation_config_id, "AblationConfig", ExperimentArtifactRole.DIAGNOSTIC),
        (
            evaluation_slice.evaluation_slice_id,
            "EvaluationSlice",
            ExperimentArtifactRole.DIAGNOSTIC,
        ),
        (
            source_snapshots.research_signal_snapshot.data_snapshot_id,
            "DataSnapshot",
            ExperimentArtifactRole.INPUT_SNAPSHOT,
        ),
        (
            source_snapshots.price_snapshot.data_snapshot_id,
            "DataSnapshot",
            ExperimentArtifactRole.INPUT_SNAPSHOT,
        ),
        (ablation_result.ablation_result_id, "AblationResult", ExperimentArtifactRole.SUMMARY),
    ]:
        artifacts.append(
            _experiment_artifact(
                experiment=experiment,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                artifact_role=artifact_role,
                storage_by_artifact_id=storage_by_artifact_id,
                clock=clock,
                workflow_run_id=workflow_run_id,
                produced_at=now,
            )
        )
    for spec in strategy_specs:
        artifacts.append(
            _experiment_artifact(
                experiment=experiment,
                artifact_id=spec.strategy_spec_id,
                artifact_type="StrategySpec",
                artifact_role=ExperimentArtifactRole.DIAGNOSTIC,
                storage_by_artifact_id=storage_by_artifact_id,
                clock=clock,
                workflow_run_id=workflow_run_id,
                produced_at=spec.updated_at,
            )
        )
    for variant in strategy_variants:
        artifacts.append(
            _experiment_artifact(
                experiment=experiment,
                artifact_id=variant.strategy_variant_id,
                artifact_type="StrategyVariant",
                artifact_role=ExperimentArtifactRole.DIAGNOSTIC,
                storage_by_artifact_id=storage_by_artifact_id,
                clock=clock,
                workflow_run_id=workflow_run_id,
                produced_at=variant.updated_at,
            )
        )
    for child_experiment in child_experiments:
        child_location = storage_by_artifact_id.get(child_experiment.experiment_id)
        artifacts.append(
            ExperimentArtifact(
                experiment_artifact_id=make_canonical_id(
                    "eart",
                    experiment.experiment_id,
                    child_experiment.experiment_id,
                ),
                experiment_id=experiment.experiment_id,
                artifact_id=child_experiment.experiment_id,
                artifact_type="Experiment",
                artifact_role=ExperimentArtifactRole.DIAGNOSTIC,
                artifact_storage_location_id=(
                    child_location.artifact_storage_location_id
                    if child_location is not None
                    else None
                ),
                uri=(
                    child_location.uri
                    if child_location is not None
                    else (
                        experiment_root.resolve().as_uri()
                        + f"/experiments/{child_experiment.experiment_id}.json"
                    )
                ),
                produced_at=child_experiment.updated_at,
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day9_ablation_experiment_artifact",
                    upstream_artifact_ids=[child_experiment.experiment_id],
                    workflow_run_id=workflow_run_id,
                ),
                created_at=now,
                updated_at=now,
            )
        )
    return artifacts


def build_parent_experiment_metrics(
    *,
    experiment: Experiment,
    ablation_result: AblationResult,
    clock: Clock,
    workflow_run_id: str,
) -> list[ExperimentMetric]:
    """Build parent experiment metrics summarizing the variant comparison rows."""

    now = clock.now()
    metrics: list[ExperimentMetric] = []
    for result in ablation_result.variant_results:
        metrics.extend(
            [
                _experiment_metric(
                    experiment=experiment,
                    metric_name=f"gross_pnl:{result.strategy_variant_id}",
                    numeric_value=result.gross_pnl,
                    source_artifact_id=result.performance_summary_id,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    recorded_at=now,
                ),
                _experiment_metric(
                    experiment=experiment,
                    metric_name=f"net_pnl:{result.strategy_variant_id}",
                    numeric_value=result.net_pnl,
                    source_artifact_id=result.performance_summary_id,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    recorded_at=now,
                ),
                _experiment_metric(
                    experiment=experiment,
                    metric_name=f"trade_count:{result.strategy_variant_id}",
                    numeric_value=float(result.trade_count),
                    source_artifact_id=result.performance_summary_id,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    recorded_at=now,
                ),
                _experiment_metric(
                    experiment=experiment,
                    metric_name=f"turnover_notional:{result.strategy_variant_id}",
                    numeric_value=result.turnover_notional,
                    source_artifact_id=result.performance_summary_id,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    recorded_at=now,
                ),
            ]
        )
    return metrics


def _spec_definition(
    family: StrategyFamily,
) -> tuple[str, str, list[str], str]:
    """Return the static strategy-spec definition for one family."""

    if family is StrategyFamily.NAIVE_BASELINE:
        return (
            "naive_hold_cash_baseline",
            "Mechanical hold-cash baseline used to keep the framework honest.",
            ["synthetic_daily_prices"],
            "hold_cash",
        )
    if family is StrategyFamily.PRICE_ONLY_BASELINE:
        return (
            "price_only_momentum_3bar",
            "Mechanical 3-bar close-to-close momentum baseline.",
            ["synthetic_daily_prices"],
            "three_bar_close_momentum",
        )
    if family is StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE:
        return (
            "text_only_candidate_signal",
            "Direct comparable adaptation of the existing Day 5 text-only candidate signals.",
            ["candidate_signals"],
            "adapt_candidate_signal",
        )
    return (
        "combined_text_price_50_50",
        "Mechanical 50/50 blend of text-only candidate signals and 3-bar price momentum.",
        ["candidate_signals", "synthetic_daily_prices"],
        "blend_text_and_price",
    )


def _default_variant_parameters(
    *,
    family: StrategyFamily,
    clock: Clock,
    workflow_run_id: str,
) -> list[ExperimentParameter]:
    """Return deterministic parameter rows for the default Day 9 variants."""

    parameter_specs: list[tuple[str, str, ExperimentParameterValueType]] = []
    if family is StrategyFamily.NAIVE_BASELINE:
        parameter_specs = [("mode", "hold_cash", ExperimentParameterValueType.STRING)]
    elif family is StrategyFamily.PRICE_ONLY_BASELINE:
        parameter_specs = [
            ("lookback_bars", "3", ExperimentParameterValueType.INTEGER),
            ("score_scale", "0.05", ExperimentParameterValueType.FLOAT),
            ("positive_threshold", "0.25", ExperimentParameterValueType.FLOAT),
            ("negative_threshold", "-0.25", ExperimentParameterValueType.FLOAT),
        ]
    elif family is StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE:
        parameter_specs = [
            ("mode", "adapt_candidate_signals", ExperimentParameterValueType.STRING),
        ]
    else:
        parameter_specs = [
            ("text_weight", "0.5", ExperimentParameterValueType.FLOAT),
            ("price_weight", "0.5", ExperimentParameterValueType.FLOAT),
            ("lookback_bars", "3", ExperimentParameterValueType.INTEGER),
        ]

    now = clock.now()
    return [
        ExperimentParameter(
            experiment_parameter_id=make_canonical_id(
                "eparam",
                "strategy_variant",
                family.value,
                key,
                value_repr,
            ),
            key=key,
            value_repr=value_repr,
            value_type=value_type,
            redacted=False,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day9_strategy_variant_parameter",
                workflow_run_id=workflow_run_id,
                notes=[f"family={family.value}"],
            ),
            created_at=now,
            updated_at=now,
        )
        for key, value_repr, value_type in parameter_specs
    ]


def _ablation_experiment_parameters(
    *,
    ablation_config: AblationConfig,
    strategy_specs: list[StrategySpec],
    clock: Clock,
    workflow_run_id: str,
) -> list[ExperimentParameter]:
    """Flatten the parent ablation config into experiment-parameter rows."""

    raw_parameters: list[tuple[str, str, ExperimentParameterValueType]] = [
        ("name", ablation_config.name, ExperimentParameterValueType.STRING),
        (
            "comparison_metric_name",
            ablation_config.comparison_metric_name,
            ExperimentParameterValueType.STRING,
        ),
        (
            "variant_families",
            json.dumps(
                [variant.family.value for variant in ablation_config.strategy_variants],
                sort_keys=True,
            ),
            ExperimentParameterValueType.ENUM,
        ),
        (
            "strategy_spec_ids",
            json.dumps([spec.strategy_spec_id for spec in strategy_specs], sort_keys=True),
            ExperimentParameterValueType.STRING,
        ),
        (
            "test_start",
            ablation_config.evaluation_slice.test_start.isoformat(),
            ExperimentParameterValueType.DATE,
        ),
        (
            "test_end",
            ablation_config.evaluation_slice.test_end.isoformat(),
            ExperimentParameterValueType.DATE,
        ),
        (
            "decision_frequency",
            ablation_config.evaluation_slice.decision_frequency,
            ExperimentParameterValueType.STRING,
        ),
        (
            "price_fixture_path",
            ablation_config.evaluation_slice.price_fixture_path,
            ExperimentParameterValueType.PATH,
        ),
        (
            "record_experiment",
            str(ablation_config.record_experiment).lower(),
            ExperimentParameterValueType.BOOLEAN,
        ),
        (
            "shared_backtest_config_id",
            ablation_config.shared_backtest_config.backtest_config_id,
            ExperimentParameterValueType.STRING,
        ),
        (
            "execution_lag_bars",
            str(ablation_config.shared_backtest_config.execution_assumption.execution_lag_bars),
            ExperimentParameterValueType.INTEGER,
        ),
        (
            "transaction_cost_bps",
            str(ablation_config.shared_backtest_config.execution_assumption.transaction_cost_bps),
            ExperimentParameterValueType.FLOAT,
        ),
        (
            "slippage_bps",
            str(ablation_config.shared_backtest_config.execution_assumption.slippage_bps),
            ExperimentParameterValueType.FLOAT,
        ),
    ]
    if ablation_config.evaluation_slice.as_of_time is not None:
        raw_parameters.append(
            (
                "as_of_time",
                ablation_config.evaluation_slice.as_of_time.isoformat(),
                ExperimentParameterValueType.DATETIME,
            )
        )

    now = clock.now()
    return [
        ExperimentParameter(
            experiment_parameter_id=make_canonical_id(
                "eparam",
                "strategy_ablation_workflow",
                key,
                value_repr,
            ),
            key=key,
            value_repr=value_repr,
            value_type=value_type,
            redacted=False,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day9_ablation_experiment_parameter",
                upstream_artifact_ids=[ablation_config.ablation_config_id],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )
        for key, value_repr, value_type in raw_parameters
    ]


def _experiment_artifact(
    *,
    experiment: Experiment,
    artifact_id: str,
    artifact_type: str,
    artifact_role: ExperimentArtifactRole,
    storage_by_artifact_id: dict[str, ArtifactStorageLocation],
    clock: Clock,
    workflow_run_id: str,
    produced_at: datetime,
) -> ExperimentArtifact:
    """Build one experiment-artifact record from a persisted ablation artifact."""

    storage_location = storage_by_artifact_id.get(artifact_id)
    return ExperimentArtifact(
        experiment_artifact_id=make_canonical_id(
            "eart",
            experiment.experiment_id,
            artifact_id,
        ),
        experiment_id=experiment.experiment_id,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_role=artifact_role,
        artifact_storage_location_id=(
            storage_location.artifact_storage_location_id if storage_location is not None else None
        ),
        uri=storage_location.uri if storage_location is not None else f"artifact://{artifact_id}",
        produced_at=produced_at,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day9_ablation_experiment_artifact",
            upstream_artifact_ids=[artifact_id],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _experiment_metric(
    *,
    experiment: Experiment,
    metric_name: str,
    numeric_value: float,
    source_artifact_id: str,
    clock: Clock,
    workflow_run_id: str,
    recorded_at: datetime,
) -> ExperimentMetric:
    """Build one parent ablation experiment metric."""

    return ExperimentMetric(
        experiment_metric_id=make_canonical_id(
            "emetric",
            experiment.experiment_id,
            metric_name,
        ),
        experiment_id=experiment.experiment_id,
        metric_name=metric_name,
        numeric_value=numeric_value,
        source_artifact_id=source_artifact_id,
        recorded_at=recorded_at,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day9_ablation_experiment_metric",
            upstream_artifact_ids=[source_artifact_id],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _bars_in_slice(
    *,
    inputs: LoadedStrategyInputs,
    evaluation_slice: EvaluationSlice,
) -> list[SyntheticDailyPriceBar]:
    """Return price bars overlapping the configured evaluation slice."""

    bars = [
        bar
        for bar in inputs.price_fixture.bars
        if evaluation_slice.test_start <= bar.timestamp_dt.date() <= evaluation_slice.test_end
    ]
    if len(bars) < 2:
        raise ValueError("Strategy ablation requires at least two price bars in the evaluation slice.")
    return bars


def _text_signals_in_slice(
    *,
    inputs: LoadedStrategyInputs,
    evaluation_slice: EvaluationSlice,
) -> list[Signal]:
    """Return text signals overlapping the configured evaluation slice."""

    return [
        signal
        for signal in sorted(inputs.text_signals, key=lambda item: item.effective_at)
        if evaluation_slice.test_start <= signal.effective_at.date() <= evaluation_slice.test_end
    ]


def _ablation_view_for_family(family: StrategyFamily) -> AblationView:
    """Map a strategy family into the closest honest ablation slice label."""

    if family is StrategyFamily.NAIVE_BASELINE:
        return AblationView.NAIVE
    if family is StrategyFamily.PRICE_ONLY_BASELINE:
        return AblationView.PRICE_ONLY
    if family is StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE:
        return AblationView.TEXT_ONLY
    return AblationView.COMBINED


def _score_to_stance(score: float) -> ResearchStance:
    """Map a comparable score into the standard research stance."""

    if score >= 0.25:
        return ResearchStance.POSITIVE
    if score <= -0.25:
        return ResearchStance.NEGATIVE
    return ResearchStance.MONITOR


def _clamp(value: float, lower: float, upper: float) -> float:
    """Clamp one numeric score into the configured range."""

    return max(lower, min(upper, value))


def _comparison_metric_value(*, result: AblationVariantResult, metric_name: str) -> float:
    """Return the numeric comparison value used for mechanical ordering."""

    if metric_name == "gross_pnl":
        return result.gross_pnl
    if metric_name == "trade_count":
        return float(result.trade_count)
    if metric_name == "turnover_notional":
        return result.turnover_notional
    return result.net_pnl


def _variant_signal(
    *,
    strategy_variant_id: str,
    company_id: str,
    signal_family: str,
    family: StrategyFamily,
    ablation_view: AblationView,
    effective_at: datetime,
    primary_score: float,
    summary: str,
    source_signal_ids: list[str],
    source_snapshot_ids: list[str],
    assumptions: list[str],
    uncertainties: list[str],
    clock: Clock,
    workflow_run_id: str,
    stable_suffix: str,
) -> StrategyVariantSignal:
    """Build one comparable strategy-variant signal."""

    now = clock.now()
    return StrategyVariantSignal(
        strategy_variant_signal_id=make_canonical_id(
            "vsig",
            strategy_variant_id,
            stable_suffix,
            ensure_utc(effective_at).isoformat(),
        ),
        strategy_variant_id=strategy_variant_id,
        company_id=company_id,
        signal_family=signal_family,
        family=family,
        ablation_view=ablation_view,
        stance=_score_to_stance(primary_score),
        primary_score=primary_score,
        effective_at=ensure_utc(effective_at),
        expires_at=None,
        status=SignalStatus.CANDIDATE,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        summary=summary,
        source_signal_ids=source_signal_ids,
        source_snapshot_ids=source_snapshot_ids,
        assumptions=assumptions,
        uncertainties=uncertainties,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day9_strategy_variant_signal",
            source_reference_ids=[],
            upstream_artifact_ids=[*source_signal_ids, *source_snapshot_ids],
            workflow_run_id=workflow_run_id,
            notes=[f"family={family.value}"],
        ),
        created_at=now,
        updated_at=now,
    )


class _NaiveBaselineExecutor:
    """Emit one neutral hold-cash comparable signal."""

    def materialize_signals(
        self,
        *,
        inputs: LoadedStrategyInputs,
        variant: StrategyVariant,
        evaluation_slice: EvaluationSlice,
        source_snapshots: StrategyInputSnapshots,
        clock: Clock,
        workflow_run_id: str,
    ) -> MaterializedVariantSignals:
        first_bar = _bars_in_slice(inputs=inputs, evaluation_slice=evaluation_slice)[0]
        signal = _variant_signal(
            strategy_variant_id=variant.strategy_variant_id,
            company_id=inputs.company_id,
            signal_family="naive_hold_cash_baseline",
            family=variant.family,
            ablation_view=AblationView.NAIVE,
            effective_at=first_bar.timestamp_dt,
            primary_score=0.0,
            summary="Mechanical hold-cash baseline for ablation comparison.",
            source_signal_ids=[],
            source_snapshot_ids=[source_snapshots.price_snapshot.data_snapshot_id],
            assumptions=["No directional forecast is made."],
            uncertainties=["Naive baseline exists for comparability, not sophistication."],
            clock=clock,
            workflow_run_id=workflow_run_id,
            stable_suffix="hold_cash",
        )
        return MaterializedVariantSignals(
            signals=[signal],
            notes=["Naive baseline emits one neutral hold-cash comparable signal."],
        )


class _TextOnlyCandidateExecutor:
    """Adapt existing Day 5 text signals into comparable variant signals."""

    def materialize_signals(
        self,
        *,
        inputs: LoadedStrategyInputs,
        variant: StrategyVariant,
        evaluation_slice: EvaluationSlice,
        source_snapshots: StrategyInputSnapshots,
        clock: Clock,
        workflow_run_id: str,
    ) -> MaterializedVariantSignals:
        slice_signals = _text_signals_in_slice(inputs=inputs, evaluation_slice=evaluation_slice)
        comparable_signals = [
            _variant_signal(
                strategy_variant_id=variant.strategy_variant_id,
                company_id=inputs.company_id,
                signal_family="text_only_candidate_signal",
                family=variant.family,
                ablation_view=AblationView.TEXT_ONLY,
                effective_at=signal.effective_at,
                primary_score=signal.primary_score,
                summary=f"Comparable text-only signal adapted from {signal.signal_id}.",
                source_signal_ids=[signal.signal_id],
                source_snapshot_ids=[source_snapshots.research_signal_snapshot.data_snapshot_id],
                assumptions=[
                    "Research-signal scores are reused directly for mechanical comparison."
                ],
                uncertainties=[
                    "Text-derived candidate signals remain unvalidated and non-promotable."
                ],
                clock=clock,
                workflow_run_id=workflow_run_id,
                stable_suffix=signal.signal_id,
            )
            for signal in slice_signals
        ]
        notes = ["Text-only baseline adapts persisted Day 5 candidate signals 1:1."]
        if not comparable_signals:
            notes.append("No eligible text signals were available inside the evaluation slice.")
        return MaterializedVariantSignals(signals=comparable_signals, notes=notes)


class _PriceOnlyMomentumExecutor:
    """Emit deterministic 3-bar close-to-close momentum signals."""

    def materialize_signals(
        self,
        *,
        inputs: LoadedStrategyInputs,
        variant: StrategyVariant,
        evaluation_slice: EvaluationSlice,
        source_snapshots: StrategyInputSnapshots,
        clock: Clock,
        workflow_run_id: str,
    ) -> MaterializedVariantSignals:
        bars = _bars_in_slice(inputs=inputs, evaluation_slice=evaluation_slice)
        signals: list[StrategyVariantSignal] = []
        for index, bar in enumerate(bars):
            if index < 3:
                continue
            lookback_close = bars[index - 3].close
            raw_return = (bar.close / lookback_close) - 1.0
            score = _clamp(raw_return / 0.05, -1.0, 1.0)
            signals.append(
                _variant_signal(
                    strategy_variant_id=variant.strategy_variant_id,
                    company_id=inputs.company_id,
                    signal_family="price_only_momentum_3bar",
                    family=variant.family,
                    ablation_view=AblationView.PRICE_ONLY,
                    effective_at=bar.timestamp_dt,
                    primary_score=score,
                    summary="Mechanical 3-bar close-to-close momentum baseline.",
                    source_signal_ids=[],
                    source_snapshot_ids=[source_snapshots.price_snapshot.data_snapshot_id],
                    assumptions=[
                        "Momentum uses only closes visible through the current bar.",
                        "Score is normalized by a fixed 5% scale and clamped to [-1, 1].",
                    ],
                    uncertainties=[
                        "Price-only baseline is a deterministic comparator, not a validated alpha claim."
                    ],
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    stable_suffix=bar.timestamp_dt.isoformat(),
                )
            )
        notes = ["Price-only baseline uses 3-bar close-to-close momentum."]
        if len(bars) <= 3:
            notes.append("No price-only signals were emitted because the slice lacks warmup bars.")
        return MaterializedVariantSignals(signals=signals, notes=notes)


class _CombinedBaselineExecutor:
    """Blend text-only and price-only baselines with a fixed 50/50 score mix."""

    def materialize_signals(
        self,
        *,
        inputs: LoadedStrategyInputs,
        variant: StrategyVariant,
        evaluation_slice: EvaluationSlice,
        source_snapshots: StrategyInputSnapshots,
        clock: Clock,
        workflow_run_id: str,
    ) -> MaterializedVariantSignals:
        text_result = _TextOnlyCandidateExecutor().materialize_signals(
            inputs=inputs,
            variant=variant,
            evaluation_slice=evaluation_slice,
            source_snapshots=source_snapshots,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
        price_result = _PriceOnlyMomentumExecutor().materialize_signals(
            inputs=inputs,
            variant=variant,
            evaluation_slice=evaluation_slice,
            source_snapshots=source_snapshots,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
        text_signals = sorted(text_result.signals, key=lambda signal: signal.effective_at)
        combined_signals: list[StrategyVariantSignal] = []

        for price_signal in price_result.signals:
            eligible_text_signals = [
                signal
                for signal in text_signals
                if signal.effective_at <= price_signal.effective_at
            ]
            if not eligible_text_signals:
                continue
            latest_text_signal = eligible_text_signals[-1]
            combined_score = _clamp(
                (0.5 * latest_text_signal.primary_score) + (0.5 * price_signal.primary_score),
                -1.0,
                1.0,
            )
            combined_signals.append(
                _variant_signal(
                    strategy_variant_id=variant.strategy_variant_id,
                    company_id=inputs.company_id,
                    signal_family="combined_text_price_50_50",
                    family=variant.family,
                    ablation_view=AblationView.COMBINED,
                    effective_at=price_signal.effective_at,
                    primary_score=combined_score,
                    summary="Mechanical 50/50 blend of text-only candidate and price-only momentum signals.",
                    source_signal_ids=list(latest_text_signal.source_signal_ids),
                    source_snapshot_ids=[
                        source_snapshots.research_signal_snapshot.data_snapshot_id,
                        source_snapshots.price_snapshot.data_snapshot_id,
                    ],
                    assumptions=[
                        "Text and price components receive equal fixed weights.",
                        "Combined signals are emitted only when both components exist.",
                    ],
                    uncertainties=[
                        "Combined baseline is a mechanical comparator and not a validated model."
                    ],
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    stable_suffix=price_signal.effective_at.isoformat(),
                )
            )

        notes = [
            "Combined baseline uses a fixed 50/50 blend of text-only and price-only scores.",
        ]
        if not combined_signals:
            notes.append(
                "No combined signals were emitted because both eligible text and price inputs were not yet available."
            )
        return MaterializedVariantSignals(signals=combined_signals, notes=notes)
