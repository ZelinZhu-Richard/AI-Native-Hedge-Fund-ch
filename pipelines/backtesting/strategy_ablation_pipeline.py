from __future__ import annotations

from pathlib import Path

from libraries.core import (
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_path,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.schemas import AblationConfig
from libraries.time import Clock, SystemClock
from services.backtesting import (
    BacktestingService,
    RunStrategyAblationWorkflowRequest,
    RunStrategyAblationWorkflowResponse,
)


def run_strategy_ablation_pipeline(
    *,
    ablation_config: AblationConfig,
    price_fixture_path: Path,
    signal_root: Path | None = None,
    signal_arbitration_root: Path | None = None,
    feature_root: Path | None = None,
    output_root: Path | None = None,
    experiment_root: Path | None = None,
    evaluation_root: Path | None = None,
    company_id: str | None = None,
    clock: Clock | None = None,
) -> RunStrategyAblationWorkflowResponse:
    """Run the deterministic Day 9 baseline strategy ablation pipeline."""

    if feature_root is not None:
        workspace = resolve_artifact_workspace_from_stage_root(feature_root)
    elif signal_root is not None:
        workspace = resolve_artifact_workspace_from_stage_root(signal_root)
    elif output_root is not None:
        workspace = resolve_artifact_workspace_from_path(
            output_root,
            stage_directory_name="ablation",
        )
    else:
        workspace = resolve_artifact_workspace()
    resolved_signal_root = signal_root or workspace.signal_root
    resolved_signal_arbitration_root = signal_arbitration_root or workspace.signal_arbitration_root
    resolved_feature_root = feature_root or workspace.signal_root
    resolved_output_root = output_root or workspace.ablation_root
    resolved_experiment_root = experiment_root or workspace.experiments_root
    resolved_evaluation_root = evaluation_root or workspace.evaluation_root
    resolved_clock = clock or SystemClock()

    service = BacktestingService(clock=resolved_clock)
    return service.run_strategy_ablation_workflow(
        RunStrategyAblationWorkflowRequest(
            signal_root=resolved_signal_root,
            signal_arbitration_root=resolved_signal_arbitration_root,
            feature_root=resolved_feature_root,
            price_fixture_path=price_fixture_path,
            output_root=resolved_output_root,
            experiment_root=resolved_experiment_root,
            evaluation_root=resolved_evaluation_root,
            company_id=company_id,
            ablation_config=ablation_config,
        )
    )
