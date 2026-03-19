from __future__ import annotations

from pathlib import Path

from libraries.config import get_settings
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
    feature_root: Path | None = None,
    output_root: Path | None = None,
    experiment_root: Path | None = None,
    evaluation_root: Path | None = None,
    company_id: str | None = None,
    clock: Clock | None = None,
) -> RunStrategyAblationWorkflowResponse:
    """Run the deterministic Day 9 baseline strategy ablation pipeline."""

    settings = get_settings()
    resolved_artifact_root = settings.resolved_artifact_root
    resolved_signal_root = signal_root or (resolved_artifact_root / "signal_generation")
    resolved_feature_root = feature_root or (resolved_artifact_root / "signal_generation")
    resolved_output_root = output_root or (resolved_artifact_root / "ablation")
    resolved_clock = clock or SystemClock()

    service = BacktestingService(clock=resolved_clock)
    return service.run_strategy_ablation_workflow(
        RunStrategyAblationWorkflowRequest(
            signal_root=resolved_signal_root,
            feature_root=resolved_feature_root,
            price_fixture_path=price_fixture_path,
            output_root=resolved_output_root,
            experiment_root=experiment_root,
            evaluation_root=evaluation_root,
            company_id=company_id,
            ablation_config=ablation_config,
        )
    )
