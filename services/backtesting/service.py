from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import StrictModel
from libraries.time import utc_now
from libraries.utils import make_prefixed_id


class BacktestRequest(StrictModel):
    """Request to evaluate a signal family under explicit temporal controls."""

    experiment_name: str = Field(description="Human-readable experiment name.")
    signal_family: str = Field(description="Signal family to evaluate.")
    universe_definition: str = Field(description="Point-in-time universe definition.")
    test_start: date = Field(description="Out-of-sample start date.")
    test_end: date = Field(description="Out-of-sample end date.")
    requested_by: str = Field(description="Requester identifier.")


class BacktestResponse(StrictModel):
    """Response returned after accepting a backtest request."""

    backtest_run_id: str = Field(description="Reserved backtest run identifier.")
    status: str = Field(description="Operational status.")
    queued_at: datetime = Field(description="UTC timestamp when the backtest was queued.")
    notes: list[str] = Field(
        default_factory=list, description="Operational notes or guardrail reminders."
    )


class BacktestingService(BaseService):
    """Run temporally disciplined backtests against point-in-time datasets."""

    capability_name = "backtesting"
    capability_description = "Runs backtests with explicit temporal boundaries and hygiene checks."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Signal", "DataSnapshot"],
            produces=["BacktestRun", "evaluation artifacts"],
            api_routes=[],
        )

    def run_backtest(self, request: BacktestRequest) -> BacktestResponse:
        """Queue a backtest for future execution."""

        return BacktestResponse(
            backtest_run_id=make_prefixed_id("btrun"),
            status="queued",
            queued_at=utc_now(),
            notes=["No performance claims are produced by Day 1 stubs."],
        )
