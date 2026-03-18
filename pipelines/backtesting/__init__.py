"""Local backtesting pipeline entrypoints."""

from pipelines.backtesting.backtest_pipeline import run_backtest_pipeline
from pipelines.backtesting.strategy_ablation_pipeline import run_strategy_ablation_pipeline

__all__ = ["run_backtest_pipeline", "run_strategy_ablation_pipeline"]
