"""Pipeline entrypoints and workflow modules."""

from typing import TYPE_CHECKING

from pipelines.backtesting import run_backtest_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.demo import run_end_to_end_demo
from pipelines.portfolio import run_portfolio_review_pipeline
from pipelines.signal_generation import run_feature_signal_pipeline

if TYPE_CHECKING:
    from pipelines.daily_operations import run_daily_workflow

__all__ = [
    "run_backtest_pipeline",
    "run_daily_workflow",
    "run_end_to_end_demo",
    "run_feature_signal_pipeline",
    "run_hypothesis_workflow_pipeline",
    "run_portfolio_review_pipeline",
]


def __getattr__(name: str) -> object:
    """Lazily expose daily workflow entrypoints without import-time cycles."""

    if name == "run_daily_workflow":
        from pipelines.daily_operations import run_daily_workflow

        return run_daily_workflow
    raise AttributeError(name)
