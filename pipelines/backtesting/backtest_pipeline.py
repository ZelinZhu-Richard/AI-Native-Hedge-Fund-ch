from __future__ import annotations

from pathlib import Path

from libraries.core import (
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_path,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.schemas import BacktestConfig
from libraries.time import Clock, SystemClock
from services.backtesting import (
    BacktestingService,
    RunBacktestWorkflowRequest,
    RunBacktestWorkflowResponse,
)


def run_backtest_pipeline(
    *,
    price_fixture_path: Path,
    backtest_config: BacktestConfig,
    signal_root: Path | None = None,
    signal_arbitration_root: Path | None = None,
    feature_root: Path | None = None,
    output_root: Path | None = None,
    company_id: str | None = None,
    record_experiment: bool = True,
    experiment_name: str | None = None,
    experiment_objective: str | None = None,
    experiment_root: Path | None = None,
    requested_by: str = "pipeline_backtesting",
    clock: Clock | None = None,
) -> RunBacktestWorkflowResponse:
    """Run the deterministic Day 6 exploratory backtesting pipeline."""

    if feature_root is not None:
        workspace = resolve_artifact_workspace_from_stage_root(feature_root)
    elif signal_root is not None:
        workspace = resolve_artifact_workspace_from_stage_root(signal_root)
    elif output_root is not None:
        workspace = resolve_artifact_workspace_from_path(
            output_root,
            stage_directory_name="backtesting",
        )
    else:
        workspace = resolve_artifact_workspace()
    resolved_signal_root = signal_root or workspace.signal_root
    resolved_signal_arbitration_root = signal_arbitration_root or workspace.signal_arbitration_root
    resolved_feature_root = feature_root or workspace.signal_root
    resolved_output_root = output_root or workspace.backtesting_root
    resolved_experiment_root = experiment_root or workspace.experiments_root
    resolved_clock = clock or SystemClock()

    service = BacktestingService(clock=resolved_clock)
    return service.run_backtest_workflow(
        RunBacktestWorkflowRequest(
            signal_root=resolved_signal_root,
            signal_arbitration_root=resolved_signal_arbitration_root,
            feature_root=resolved_feature_root,
            price_fixture_path=price_fixture_path,
            output_root=resolved_output_root,
            company_id=company_id,
            backtest_config=backtest_config,
            record_experiment=record_experiment,
            experiment_name=experiment_name,
            experiment_objective=experiment_objective,
            experiment_root=resolved_experiment_root,
            requested_by=requested_by,
        )
    )
