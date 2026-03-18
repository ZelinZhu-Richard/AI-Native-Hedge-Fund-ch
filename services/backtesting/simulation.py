from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    BacktestConfig,
    BacktestRun,
    BacktestStatus,
    BenchmarkKind,
    BenchmarkReference,
    DataLayer,
    DataSnapshot,
    DecisionAction,
    ExecutionAssumption,
    PerformanceSummary,
    ResearchStance,
    Signal,
    SimulationEvent,
    SimulationEventType,
    StrategyDecision,
    StrategyFamily,
    StrategyVariantSignal,
    StrictModel,
)
from libraries.time import Clock, ensure_utc
from libraries.utils import make_canonical_id
from services.backtesting.loaders import (
    LoadedBacktestInputs,
    SyntheticDailyPriceBar,
)


@dataclass(frozen=True)
class PendingFill:
    """Scheduled next-bar fill created from one strategy decision."""

    strategy_decision_id: str
    target_units: int


class BacktestComputationResult(StrictModel):
    """Structured output of the deterministic Day 6 backtesting workflow."""

    backtest_run: BacktestRun = Field(description="Completed exploratory backtest run artifact.")
    data_snapshots: list[DataSnapshot] = Field(
        default_factory=list,
        description="Signal and price snapshots used by the run.",
    )
    strategy_decisions: list[StrategyDecision] = Field(
        default_factory=list,
        description="Point-in-time decisions emitted by the strategy rule.",
    )
    simulation_events: list[SimulationEvent] = Field(
        default_factory=list,
        description="Simulation events emitted during execution and marking.",
    )
    performance_summary: PerformanceSummary = Field(
        description="Mechanical performance summary for the exploratory run."
    )
    benchmark_references: list[BenchmarkReference] = Field(
        default_factory=list,
        description="Mechanical benchmark references emitted for the run.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes, simplifications, and skipped-work explanations.",
    )


ComparableSignal = Signal | StrategyVariantSignal


def run_backtest_simulation(
    *,
    inputs: LoadedBacktestInputs,
    config: BacktestConfig,
    clock: Clock,
    workflow_run_id: str,
    backtest_run_id: str,
) -> BacktestComputationResult:
    """Run the deterministic Day 6 exploratory backtest skeleton."""

    bars = _bars_in_window(inputs=inputs, config=config)
    signal_snapshot = _build_signal_snapshot(
        inputs=inputs,
        config=config,
        clock=clock,
        workflow_run_id=workflow_run_id,
    )
    price_snapshot = _build_price_snapshot(
        inputs=inputs,
        config=config,
        clock=clock,
        workflow_run_id=workflow_run_id,
    )
    leakage_checks: list[str] = []
    notes: list[str] = [
        "Day 6 backtests are exploratory-only and use candidate signals as explicit dev inputs.",
        "Synthetic daily price fixtures are mechanical test infrastructure, not market realism.",
    ]
    _append_unique(
        leakage_checks,
        (
            "signal_snapshot_cutoff_check:passed"
            if signal_snapshot.information_cutoff_time is not None
            else "signal_snapshot_cutoff_check:failed"
        ),
    )
    _append_unique(
        leakage_checks,
        (
            "price_snapshot_cutoff_check:passed"
            if price_snapshot.information_cutoff_time is not None
            else "price_snapshot_cutoff_check:failed"
        ),
    )

    first_available_bar_date = bars[0].timestamp_dt.date()
    last_available_bar_date = bars[-1].timestamp_dt.date()
    if config.test_start < first_available_bar_date or config.test_end > last_available_bar_date:
        _append_unique(
            leakage_checks,
            "price_window_coverage_check:requested_window_outside_available_price_bars",
        )
        notes.append(
            "Requested backtest window extends beyond the synthetic price fixture; the run uses the available overlap only."
        )
    else:
        _append_unique(leakage_checks, "price_window_coverage_check:passed")

    missing_lineage_signals = [
        _signal_id(signal)
        for signal in inputs.signals
        if not _signal_has_traceability(signal=signal, inputs=inputs)
    ]
    if missing_lineage_signals:
        for signal_id in missing_lineage_signals:
            _append_unique(leakage_checks, f"signal_lineage_check:failed:{signal_id}")
    else:
        _append_unique(leakage_checks, "signal_lineage_check:passed")

    execution_assumption = config.execution_assumption
    symbol = inputs.price_fixture.symbol
    decisions: list[StrategyDecision] = []
    events: list[SimulationEvent] = []
    current_units = 0
    cash = config.starting_cash
    total_costs = 0.0
    turnover_notional = 0.0
    trade_count = 0
    pending_fills: dict[int, PendingFill] = {}

    source_reference_ids = _source_reference_ids(inputs=inputs)
    events.append(
        _event(
            backtest_run_id=backtest_run_id,
            event_id=make_canonical_id("sevt", backtest_run_id, "run_started"),
            event_type=SimulationEventType.RUN_STARTED,
            event_time=bars[0].timestamp_dt,
            symbol=symbol,
            quantity=current_units,
            price=bars[0].open,
            cash_delta=0.0,
            position_after_units=current_units,
            note="Exploratory backtest run started.",
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        )
    )

    for index, bar in enumerate(bars):
        decision_time = bar.timestamp_dt

        if index in pending_fills:
            pending_fill = pending_fills.pop(index)
            fill_quantity = pending_fill.target_units - current_units
            notional = float(fill_quantity) * bar.open
            transaction_cost = abs(notional) * (
                execution_assumption.transaction_cost_bps / 10_000.0
            )
            slippage = abs(notional) * (execution_assumption.slippage_bps / 10_000.0)
            cash_delta = -(notional + transaction_cost + slippage)
            cash += cash_delta
            total_costs += transaction_cost + slippage
            turnover_notional += abs(notional)
            current_units = pending_fill.target_units
            trade_count += 1
            events.append(
                _event(
                    backtest_run_id=backtest_run_id,
                    event_id=make_canonical_id(
                        "sevt", backtest_run_id, pending_fill.strategy_decision_id, "fill"
                    ),
                    strategy_decision_id=pending_fill.strategy_decision_id,
                    event_type=SimulationEventType.FILL,
                    event_time=decision_time,
                    symbol=symbol,
                    quantity=fill_quantity,
                    price=bar.open,
                    transaction_cost_applied=transaction_cost,
                    slippage_applied=slippage,
                    cash_delta=cash_delta,
                    position_after_units=current_units,
                    note="Executed scheduled next-bar open fill.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                )
            )

        selected_signal = _select_signal_for_decision(
            inputs=inputs,
            config=config,
            decision_time=decision_time,
            leakage_checks=leakage_checks,
        )
        proposed_target = (
            _target_units_from_stance(selected_signal.stance)
            if selected_signal is not None
            else 0
        )
        action = _action_for_target(current_units=current_units, target_units=proposed_target)
        target_units = proposed_target
        reason = (
            "No eligible signal available by the current decision cutoff."
            if selected_signal is None
            else (
                "Latest eligible signal selected under the Day 6 rule: "
                f"{selected_signal.signal_id} ({selected_signal.stance.value}, "
                f"score={selected_signal.primary_score:.4f})."
            )
        )
        next_fill_index = index + execution_assumption.execution_lag_bars
        if target_units != current_units and next_fill_index >= len(bars):
            action = DecisionAction.SKIP_SIGNAL
            target_units = current_units
            reason += " No future bar exists for next-bar execution, so the decision is recorded but not filled."
            notes.append("Terminal signal change skipped because no future bar was available for execution.")

        strategy_decision_id = make_canonical_id(
            "sdec",
            backtest_run_id,
            decision_time.isoformat(),
            selected_signal.signal_id if selected_signal is not None else action.value,
        )
        decision = StrategyDecision(
            strategy_decision_id=strategy_decision_id,
            backtest_run_id=backtest_run_id,
            company_id=inputs.company_id,
            signal_id=selected_signal.signal_id if selected_signal is not None else None,
            decision_time=decision_time,
            signal_effective_at=selected_signal.effective_at if selected_signal is not None else None,
            action=action,
            target_units=target_units,
            decision_snapshot_id=signal_snapshot.data_snapshot_id,
            reason=reason,
            assumptions=[
                f"decision_rule={config.decision_rule}",
                f"execution_lag_bars={execution_assumption.execution_lag_bars}",
                f"decision_frequency={config.decision_frequency}",
            ],
            provenance=build_provenance(
                clock=clock,
                transformation_name="day6_strategy_decision",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=(
                    [_signal_id(selected_signal)] if selected_signal is not None else []
                ),
                workflow_run_id=workflow_run_id,
                notes=[f"backtest_run_id={backtest_run_id}"],
            ),
            created_at=clock.now(),
            updated_at=clock.now(),
        )
        decisions.append(decision)
        events.append(
            _event(
                backtest_run_id=backtest_run_id,
                event_id=make_canonical_id("sevt", backtest_run_id, strategy_decision_id, "decision"),
                strategy_decision_id=strategy_decision_id,
                event_type=SimulationEventType.DECISION,
                event_time=decision_time,
                symbol=symbol,
                quantity=target_units,
                price=bar.close,
                cash_delta=0.0,
                position_after_units=current_units,
                note=reason,
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )

        if target_units != current_units and action is not DecisionAction.SKIP_SIGNAL:
            pending_fills[next_fill_index] = PendingFill(
                strategy_decision_id=strategy_decision_id,
                target_units=target_units,
            )

        portfolio_value = cash + (float(current_units) * bar.close)
        events.append(
            _event(
                backtest_run_id=backtest_run_id,
                event_id=make_canonical_id("sevt", backtest_run_id, decision_time.isoformat(), "mark"),
                event_type=SimulationEventType.MARK,
                event_time=decision_time,
                symbol=symbol,
                quantity=current_units,
                price=bar.close,
                cash_delta=0.0,
                position_after_units=current_units,
                note=f"Marked account equity at {portfolio_value:.2f}.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )

    ending_value = cash + (float(current_units) * bars[-1].close)
    gross_ending_value = ending_value + total_costs
    benchmark_references = _build_benchmarks(
        backtest_run_id=backtest_run_id,
        config=config,
        bars=bars,
        symbol=symbol,
        clock=clock,
        workflow_run_id=workflow_run_id,
        source_reference_ids=source_reference_ids,
    )
    performance_summary = PerformanceSummary(
        performance_summary_id=make_canonical_id("psum", backtest_run_id),
        backtest_run_id=backtest_run_id,
        starting_cash=config.starting_cash,
        ending_cash=ending_value,
        gross_pnl=gross_ending_value - config.starting_cash,
        net_pnl=ending_value - config.starting_cash,
        trade_count=trade_count,
        turnover_notional=turnover_notional,
        benchmark_reference_ids=[
            benchmark.benchmark_reference_id for benchmark in benchmark_references
        ],
        notes=[
            "Ending cash is marked to market using the final close, not forced liquidation.",
            "No Sharpe-style or portfolio-optimization metrics are produced on Day 6.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day6_performance_summary",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[decision.strategy_decision_id for decision in decisions],
            workflow_run_id=workflow_run_id,
            notes=[f"backtest_run_id={backtest_run_id}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )

    for benchmark in benchmark_references:
        events.append(
            _event(
                backtest_run_id=backtest_run_id,
                event_id=make_canonical_id(
                    "sevt", backtest_run_id, benchmark.benchmark_reference_id, "benchmark"
                ),
                event_type=SimulationEventType.BENCHMARK_MARK,
                event_time=bars[-1].timestamp_dt,
                symbol=benchmark.symbol,
                price=benchmark.ending_value,
                cash_delta=0.0,
                position_after_units=None,
                note=(
                    f"{benchmark.benchmark_name} ending value={benchmark.ending_value:.2f}, "
                    f"simple_return={benchmark.simple_return:.6f}"
                ),
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )

    events.append(
        _event(
            backtest_run_id=backtest_run_id,
            event_id=make_canonical_id("sevt", backtest_run_id, "run_completed"),
            event_type=SimulationEventType.RUN_COMPLETED,
            event_time=bars[-1].timestamp_dt,
            symbol=symbol,
            quantity=current_units,
            price=bars[-1].close,
            cash_delta=0.0,
            position_after_units=current_units,
            note=f"Run completed with ending marked-to-market equity {ending_value:.2f}.",
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        )
    )

    backtest_run = BacktestRun(
        backtest_run_id=backtest_run_id,
        backtest_config_id=config.backtest_config_id,
        experiment_id=None,
        company_id=inputs.company_id,
        strategy_name=config.strategy_name,
        signal_family=config.signal_family,
        ablation_view=config.ablation_view,
        status=BacktestStatus.COMPLETED,
        train_start=None,
        train_end=None,
        test_start=config.test_start,
        test_end=config.test_end,
        signal_snapshot_id=signal_snapshot.data_snapshot_id,
        price_snapshot_id=price_snapshot.data_snapshot_id,
        execution_assumption_id=execution_assumption.execution_assumption_id,
        performance_summary_id=performance_summary.performance_summary_id,
        benchmark_reference_ids=[
            benchmark.benchmark_reference_id for benchmark in benchmark_references
        ],
        decision_cutoff_time=bars[-1].timestamp_dt,
        exploratory_only=config.exploratory_only,
        allowed_signal_statuses=config.signal_status_allowlist,
        leakage_checks=leakage_checks,
        notes=notes,
        result_artifact_uri=None,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day6_backtest_run",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=(
                [_signal_id(signal) for signal in inputs.signals]
                + list(inputs.features_by_id.keys())
                + [config.backtest_config_id]
            ),
            workflow_run_id=workflow_run_id,
            notes=[f"performance_summary_id={performance_summary.performance_summary_id}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )

    return BacktestComputationResult(
        backtest_run=backtest_run,
        data_snapshots=[signal_snapshot, price_snapshot],
        strategy_decisions=decisions,
        simulation_events=events,
        performance_summary=performance_summary,
        benchmark_references=benchmark_references,
        notes=notes,
    )


def _bars_in_window(
    *,
    inputs: LoadedBacktestInputs,
    config: BacktestConfig,
) -> list[SyntheticDailyPriceBar]:
    """Return sorted bars overlapping the configured test window."""

    bars = [
        bar
        for bar in inputs.price_fixture.bars
        if config.test_start <= bar.timestamp_dt.date() <= config.test_end
    ]
    if len(bars) < 2:
        raise ValueError("Backtesting requires at least two price bars inside the test window.")
    return bars


def _build_signal_snapshot(
    *,
    inputs: LoadedBacktestInputs,
    config: BacktestConfig,
    clock: Clock,
    workflow_run_id: str,
) -> DataSnapshot:
    """Build the signal snapshot metadata for the exploratory run."""

    now = clock.now()
    event_time_start = min((signal.effective_at for signal in inputs.signals), default=None)
    cutoff_time = max((signal.effective_at for signal in inputs.signals), default=None)
    ingestion_cutoff_time = max((signal.created_at for signal in inputs.signals), default=None)
    dataset_name = _signal_dataset_name(inputs=inputs)
    snapshot_time = max(now, cutoff_time) if cutoff_time is not None else now
    return DataSnapshot(
        data_snapshot_id=make_canonical_id(
            "snap",
            inputs.company_id,
            "signals",
            config.backtest_config_id,
        ),
        dataset_name=dataset_name,
        dataset_version=config.backtest_config_id,
        dataset_manifest_id=None,
        data_layer=DataLayer.DERIVED,
        snapshot_time=snapshot_time,
        event_time_start=event_time_start,
        watermark_time=cutoff_time,
        ingestion_cutoff_time=ingestion_cutoff_time,
        information_cutoff_time=cutoff_time or now,
        storage_uri=inputs.signal_root.resolve().as_uri(),
        row_count=len(inputs.signals),
        schema_version="day6_backtesting",
        partition_key=inputs.company_id,
        source_count=len(
            {
                source_reference_id
                for signal in inputs.signals
                for source_reference_id in signal.provenance.source_reference_ids
            }
        ),
        completeness_ratio=1.0,
        source_families=_signal_source_families(inputs=inputs),
        created_by_process="day6_backtesting_signal_snapshot",
        provenance=build_provenance(
            clock=clock,
            transformation_name="day6_signal_snapshot",
            source_reference_ids=_source_reference_ids(inputs=inputs),
            upstream_artifact_ids=[_signal_id(signal) for signal in inputs.signals],
            workflow_run_id=workflow_run_id,
            notes=[_signal_snapshot_note(inputs=inputs)],
        ),
        created_at=now,
        updated_at=now,
    )


def _build_price_snapshot(
    *,
    inputs: LoadedBacktestInputs,
    config: BacktestConfig,
    clock: Clock,
    workflow_run_id: str,
) -> DataSnapshot:
    """Build the synthetic price snapshot metadata for the exploratory run."""

    now = clock.now()
    event_time_start = min(bar.timestamp_dt for bar in inputs.price_fixture.bars)
    cutoff_time = max(bar.timestamp_dt for bar in inputs.price_fixture.bars)
    snapshot_time = max(now, cutoff_time)
    return DataSnapshot(
        data_snapshot_id=make_canonical_id(
            "snap",
            inputs.company_id,
            "prices",
            config.backtest_config_id,
        ),
        dataset_name="synthetic_daily_prices",
        dataset_version=config.backtest_config_id,
        dataset_manifest_id=None,
        data_layer=DataLayer.NORMALIZED,
        snapshot_time=snapshot_time,
        event_time_start=event_time_start,
        watermark_time=cutoff_time,
        ingestion_cutoff_time=None,
        information_cutoff_time=cutoff_time,
        storage_uri=inputs.price_fixture_path.resolve().as_uri(),
        row_count=len(inputs.price_fixture.bars),
        schema_version="day6_backtesting",
        partition_key=inputs.company_id,
        source_count=1,
        completeness_ratio=1.0,
        source_families=["synthetic_price_fixture"],
        created_by_process="day6_backtesting_price_snapshot",
        provenance=build_provenance(
            clock=clock,
            transformation_name="day6_price_snapshot",
            source_reference_ids=[],
            upstream_artifact_ids=[config.backtest_config_id],
            workflow_run_id=workflow_run_id,
            notes=["Synthetic price fixture is test-only and should not be treated as market data."],
        ),
        created_at=now,
        updated_at=now,
    )


def _select_signal_for_decision(
    *,
    inputs: LoadedBacktestInputs,
    config: BacktestConfig,
    decision_time: datetime,
    leakage_checks: list[str],
) -> ComparableSignal | None:
    """Return the latest eligible signal that passes temporal and lineage checks."""

    eligible: list[ComparableSignal] = []
    feature_availability_passed = False
    for signal in inputs.signals:
        if signal.status not in config.signal_status_allowlist:
            continue
        eligible_at = _eligible_signal_time(signal=signal, assumption=config.execution_assumption)
        if eligible_at > decision_time:
            continue
        if not _validate_comparable_signal(
            signal=signal,
            inputs=inputs,
            decision_time=decision_time,
            leakage_checks=leakage_checks,
        ):
            continue
        feature_availability_passed = True
        eligible.append(signal)

    if feature_availability_passed:
        _append_unique(leakage_checks, "feature_availability_check:passed")
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda signal: (
            -ensure_utc(signal.effective_at).timestamp(),
            -abs(signal.primary_score),
            _signal_id(signal),
        ),
    )[0]


def _eligible_signal_time(*, signal: ComparableSignal, assumption: ExecutionAssumption) -> datetime:
    """Return the earliest decision time when the signal is allowed into simulation."""

    effective_at = ensure_utc(signal.effective_at)
    if assumption.signal_availability_buffer_minutes is None:
        return effective_at
    return effective_at + timedelta(minutes=assumption.signal_availability_buffer_minutes)


def _target_units_from_stance(stance: ResearchStance) -> int:
    """Map a research stance into the Day 6 unit-position target."""

    if stance is ResearchStance.POSITIVE:
        return 1
    if stance is ResearchStance.NEGATIVE:
        return -1
    return 0


def _action_for_target(*, current_units: int, target_units: int) -> DecisionAction:
    """Return the strategy action implied by the current and target unit exposure."""

    if target_units == current_units:
        return (
            DecisionAction.HOLD_CASH if target_units == 0 else DecisionAction.HOLD_POSITION
        )
    if target_units == 0:
        return DecisionAction.CLOSE_POSITION
    if target_units > 0:
        return DecisionAction.OPEN_LONG
    return DecisionAction.OPEN_SHORT


def _build_benchmarks(
    *,
    backtest_run_id: str,
    config: BacktestConfig,
    bars: list[SyntheticDailyPriceBar],
    symbol: str,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> list[BenchmarkReference]:
    """Build the Day 6 flat and buy-and-hold benchmark references."""

    benchmark_references: list[BenchmarkReference] = []
    last_close = bars[-1].close
    first_executable_index = min(config.execution_assumption.execution_lag_bars, len(bars) - 1)
    first_executable_open = bars[first_executable_index].open
    buy_hold_ending_value = config.starting_cash + (last_close - first_executable_open)

    benchmark_specs = [
        (
            BenchmarkKind.FLAT_BASELINE,
            "Flat Baseline",
            None,
            config.starting_cash,
            config.starting_cash,
            ["No trades are executed."],
        ),
        (
            BenchmarkKind.BUY_AND_HOLD,
            "Buy And Hold",
            symbol,
            config.starting_cash,
            buy_hold_ending_value,
            [
                "Long one unit from the first executable bar through the end of the window.",
                "Uses the same synthetic price path as the exploratory run.",
            ],
        ),
    ]

    for benchmark_kind, benchmark_name, benchmark_symbol, starting_value, ending_value, notes in benchmark_specs:
        benchmark_references.append(
            BenchmarkReference(
                benchmark_reference_id=make_canonical_id(
                    "bench", backtest_run_id, benchmark_kind.value
                ),
                backtest_run_id=backtest_run_id,
                benchmark_name=benchmark_name,
                benchmark_kind=benchmark_kind,
                symbol=benchmark_symbol,
                starting_value=starting_value,
                ending_value=ending_value,
                simple_return=(ending_value - starting_value) / starting_value,
                notes=notes,
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="day6_benchmark_reference",
                    source_reference_ids=source_reference_ids,
                    upstream_artifact_ids=[config.backtest_config_id],
                    workflow_run_id=workflow_run_id,
                    notes=[f"benchmark_kind={benchmark_kind.value}"],
                ),
                created_at=clock.now(),
                updated_at=clock.now(),
            )
        )
    return benchmark_references


def _event(
    *,
    backtest_run_id: str,
    event_id: str,
    event_type: SimulationEventType,
    event_time: datetime,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
    strategy_decision_id: str | None = None,
    symbol: str | None = None,
    quantity: int | None = None,
    price: float | None = None,
    transaction_cost_applied: float = 0.0,
    slippage_applied: float = 0.0,
    cash_delta: float = 0.0,
    position_after_units: int | None = None,
    note: str | None = None,
) -> SimulationEvent:
    """Create one typed simulation event with standard provenance."""

    return SimulationEvent(
        simulation_event_id=event_id,
        backtest_run_id=backtest_run_id,
        strategy_decision_id=strategy_decision_id,
        event_type=event_type,
        event_time=ensure_utc(event_time),
        symbol=symbol,
        quantity=quantity,
        price=price,
        transaction_cost_applied=transaction_cost_applied,
        slippage_applied=slippage_applied,
        cash_delta=cash_delta,
        position_after_units=position_after_units,
        note=note,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day6_simulation_event",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=(
                [strategy_decision_id] if strategy_decision_id is not None else [backtest_run_id]
            ),
            workflow_run_id=workflow_run_id,
            notes=[f"event_type={event_type.value}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _source_reference_ids(*, inputs: LoadedBacktestInputs) -> list[str]:
    """Collect the source references visible through the signal and feature lineage."""

    return sorted(
        {
            source_reference_id
            for signal in inputs.signals
            for source_reference_id in _signal_source_reference_ids(signal=signal, inputs=inputs)
        }
        | {
            source_reference_id
            for feature in inputs.features_by_id.values()
            for source_reference_id in feature.provenance.source_reference_ids
        }
    )


def _append_unique(values: list[str], value: str) -> None:
    """Append a note or check string once while preserving order."""

    if value not in values:
        values.append(value)


def _signal_id(signal: ComparableSignal) -> str:
    """Return a stable comparable signal identifier."""

    return signal.signal_id if isinstance(signal, Signal) else signal.strategy_variant_signal_id


def _signal_has_traceability(*, signal: ComparableSignal, inputs: LoadedBacktestInputs) -> bool:
    """Return whether a comparable signal carries the minimum traceability for simulation."""

    if isinstance(signal, Signal):
        return bool(signal.lineage.feature_ids and signal.lineage.supporting_evidence_link_ids)
    if not signal.source_snapshot_ids:
        return False
    if signal.family in {
        StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
        StrategyFamily.COMBINED_BASELINE,
    }:
        return all(
            source_signal_id in inputs.research_signals_by_id
            for source_signal_id in signal.source_signal_ids
        )
    return True


def _signal_feature_ids(
    *,
    signal: ComparableSignal,
    inputs: LoadedBacktestInputs,
) -> list[str]:
    """Resolve comparable-signal feature dependencies for temporal revalidation."""

    if isinstance(signal, Signal):
        return list(signal.lineage.feature_ids)

    feature_ids: list[str] = []
    for source_signal_id in signal.source_signal_ids:
        source_signal = inputs.research_signals_by_id.get(source_signal_id)
        if source_signal is None:
            continue
        feature_ids.extend(source_signal.lineage.feature_ids)
    return list(dict.fromkeys(feature_ids))


def _validate_comparable_signal(
    *,
    signal: ComparableSignal,
    inputs: LoadedBacktestInputs,
    decision_time: datetime,
    leakage_checks: list[str],
) -> bool:
    """Validate traceability and feature availability for one comparable signal."""

    signal_id = _signal_id(signal)
    if isinstance(signal, Signal):
        if not signal.lineage.feature_ids:
            _append_unique(leakage_checks, f"missing_lineage:signal_without_features:{signal_id}")
            return False
        if not signal.lineage.supporting_evidence_link_ids:
            _append_unique(leakage_checks, f"missing_lineage:signal_without_evidence:{signal_id}")
            return False
    else:
        if not signal.source_snapshot_ids:
            _append_unique(leakage_checks, f"missing_lineage:signal_without_snapshot:{signal_id}")
            return False
        if signal.family in {
            StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
            StrategyFamily.COMBINED_BASELINE,
        } and not signal.source_signal_ids:
            _append_unique(
                leakage_checks,
                f"missing_lineage:variant_signal_without_source_signal:{signal_id}",
            )
            return False
        for source_signal_id in signal.source_signal_ids:
            if source_signal_id not in inputs.research_signals_by_id:
                _append_unique(
                    leakage_checks,
                    f"missing_lineage:variant_signal_missing_source_signal:{signal_id}:{source_signal_id}",
                )
                return False

    feature_ids = _signal_feature_ids(signal=signal, inputs=inputs)
    if not feature_ids:
        return True

    missing_feature_ids = [
        feature_id for feature_id in feature_ids if feature_id not in inputs.features_by_id
    ]
    if missing_feature_ids:
        for feature_id in missing_feature_ids:
            _append_unique(
                leakage_checks,
                f"missing_lineage:signal_missing_feature:{signal_id}:{feature_id}",
            )
        return False
    if any(
        inputs.features_by_id[feature_id].feature_value.available_at > decision_time
        for feature_id in feature_ids
    ):
        for feature_id in feature_ids:
            feature = inputs.features_by_id[feature_id]
            if feature.feature_value.available_at > decision_time:
                _append_unique(
                    leakage_checks,
                    (
                        "future_feature_availability_rejected:"
                        f"{signal_id}:{feature_id}:{feature.feature_value.available_at.isoformat()}"
                    ),
                )
        return False
    return True


def _signal_source_reference_ids(
    *,
    signal: ComparableSignal,
    inputs: LoadedBacktestInputs,
) -> list[str]:
    """Return source references visible through a comparable signal."""

    source_reference_ids = list(signal.provenance.source_reference_ids)
    if isinstance(signal, StrategyVariantSignal):
        for source_signal_id in signal.source_signal_ids:
            source_signal = inputs.research_signals_by_id.get(source_signal_id)
            if source_signal is not None:
                source_reference_ids.extend(source_signal.provenance.source_reference_ids)
    return list(dict.fromkeys(source_reference_ids))


def _signal_dataset_name(*, inputs: LoadedBacktestInputs) -> str:
    """Return the snapshot dataset name for the current comparable signal set."""

    if all(isinstance(signal, Signal) for signal in inputs.signals):
        return "candidate_signals"
    return "strategy_variant_signals"


def _signal_source_families(*, inputs: LoadedBacktestInputs) -> list[str]:
    """Return canonical source-family labels for the current comparable signal set."""

    if all(isinstance(signal, Signal) for signal in inputs.signals):
        return ["candidate_signals"]
    families = {
        "strategy_variant_signals",
        *[
            signal.family.value
            for signal in inputs.signals
            if isinstance(signal, StrategyVariantSignal)
        ],
    }
    return sorted(families)


def _signal_snapshot_note(*, inputs: LoadedBacktestInputs) -> str:
    """Return an honest note describing the signal snapshot source."""

    if all(isinstance(signal, Signal) for signal in inputs.signals):
        return "Signals are loaded from persisted Day 5 local artifacts."
    return "Signals are comparable variant signals materialized by the Day 9 ablation harness."
