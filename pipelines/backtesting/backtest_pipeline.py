from __future__ import annotations

from pathlib import Path

from libraries.config import get_settings
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
    feature_root: Path | None = None,
    output_root: Path | None = None,
    company_id: str | None = None,
    requested_by: str = "pipeline_backtesting",
    clock: Clock | None = None,
) -> RunBacktestWorkflowResponse:
    """Run the deterministic Day 6 exploratory backtesting pipeline."""

    settings = get_settings()
    resolved_artifact_root = settings.resolved_artifact_root
    resolved_signal_root = signal_root or (resolved_artifact_root / "signal_generation")
    resolved_feature_root = feature_root or (resolved_artifact_root / "signal_generation")
    resolved_output_root = output_root or (resolved_artifact_root / "backtesting")
    resolved_clock = clock or SystemClock()

    service = BacktestingService(clock=resolved_clock)
    return service.run_backtest_workflow(
        RunBacktestWorkflowRequest(
            signal_root=resolved_signal_root,
            feature_root=resolved_feature_root,
            price_fixture_path=price_fixture_path,
            output_root=resolved_output_root,
            company_id=company_id,
            backtest_config=backtest_config,
            requested_by=requested_by,
        )
    )
