from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    BacktestConfig,
    BacktestRun,
    BenchmarkReference,
    DataSnapshot,
    PerformanceSummary,
    SimulationEvent,
    StrategyDecision,
    StrictModel,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.utils import make_prefixed_id
from services.backtesting.loaders import load_backtest_inputs
from services.backtesting.simulation import run_backtest_simulation
from services.backtesting.storage import LocalBacktestArtifactStore


class BacktestRequest(StrictModel):
    """Request to evaluate a signal family under explicit temporal controls."""

    experiment_name: str = Field(description="Human-readable experiment name.")
    signal_family: str = Field(description="Signal family to evaluate.")
    universe_definition: str = Field(description="Point-in-time universe definition.")
    test_start: datetime = Field(description="Out-of-sample start timestamp.")
    test_end: datetime = Field(description="Out-of-sample end timestamp.")
    requested_by: str = Field(description="Requester identifier.")


class BacktestResponse(StrictModel):
    """Response returned after accepting a queued backtest request."""

    backtest_run_id: str = Field(description="Reserved backtest run identifier.")
    status: str = Field(description="Operational status.")
    queued_at: datetime = Field(description="UTC timestamp when the backtest was queued.")
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes or guardrail reminders.",
    )


class RunBacktestWorkflowRequest(StrictModel):
    """Explicit local request to run the Day 6 exploratory backtest workflow."""

    signal_root: Path = Field(description="Root path containing persisted signal artifacts.")
    feature_root: Path = Field(description="Root path containing persisted feature artifacts.")
    price_fixture_path: Path = Field(description="Path to the synthetic daily price fixture.")
    output_root: Path | None = Field(
        default=None,
        description="Optional output root for persisted backtesting artifacts.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when the signal root contains multiple companies.",
    )
    backtest_config: BacktestConfig = Field(description="Reproducible backtest configuration.")
    requested_by: str = Field(description="Requester identifier.")


class RunBacktestWorkflowResponse(StrictModel):
    """Result of the deterministic Day 6 exploratory backtesting workflow."""

    backtest_run: BacktestRun = Field(description="Completed exploratory backtest run artifact.")
    backtest_config: BacktestConfig = Field(description="Reproducible backtest configuration.")
    data_snapshots: list[DataSnapshot] = Field(
        default_factory=list,
        description="Signal and price snapshots used by the run.",
    )
    strategy_decisions: list[StrategyDecision] = Field(
        default_factory=list,
        description="Point-in-time decisions emitted by the run.",
    )
    simulation_events: list[SimulationEvent] = Field(
        default_factory=list,
        description="Simulation events emitted by the run.",
    )
    performance_summary: PerformanceSummary = Field(
        description="Mechanical performance summary for the run."
    )
    benchmark_references: list[BenchmarkReference] = Field(
        default_factory=list,
        description="Mechanical benchmarks emitted alongside the run.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing assumptions or skipped work.",
    )


class BacktestingService(BaseService):
    """Run temporally disciplined exploratory backtests against persisted artifacts."""

    capability_name = "backtesting"
    capability_description = "Runs exploratory backtests with explicit temporal cutoffs and synthetic fixtures."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Signal", "Feature", "DataSnapshot", "BacktestConfig"],
            produces=[
                "BacktestRun",
                "StrategyDecision",
                "SimulationEvent",
                "PerformanceSummary",
                "BenchmarkReference",
            ],
            api_routes=[],
        )

    def run_backtest(self, request: BacktestRequest) -> BacktestResponse:
        """Queue a backtest for future execution."""

        return BacktestResponse(
            backtest_run_id=make_prefixed_id("btrun"),
            status="queued",
            queued_at=self.clock.now(),
            notes=[
                "Day 6 queued backtests remain exploratory-only.",
                "Use run_backtest_workflow() for the deterministic local backtesting path.",
            ],
        )

    def run_backtest_workflow(
        self,
        request: RunBacktestWorkflowRequest,
    ) -> RunBacktestWorkflowResponse:
        """Execute the deterministic Day 6 exploratory backtesting workflow."""

        backtest_run_id = make_prefixed_id("btrun")
        inputs = load_backtest_inputs(
            signal_root=request.signal_root,
            feature_root=request.feature_root,
            price_fixture_path=request.price_fixture_path,
            company_id=request.company_id,
        )
        result = run_backtest_simulation(
            inputs=inputs,
            config=request.backtest_config,
            clock=self.clock,
            workflow_run_id=backtest_run_id,
            backtest_run_id=backtest_run_id,
        )
        output_root = request.output_root or (get_settings().resolved_artifact_root / "backtesting")
        store = LocalBacktestArtifactStore(root=output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []

        storage_locations.append(
            store.persist_model(
                artifact_id=request.backtest_config.backtest_config_id,
                category="configs",
                model=request.backtest_config,
                source_reference_ids=request.backtest_config.provenance.source_reference_ids,
            )
        )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="configs",
                model=request.backtest_config.execution_assumption,
            )
        )
        for snapshot in result.data_snapshots:
            storage_locations.append(
                self._persist_model(store=store, category="snapshots", model=snapshot)
            )
        for decision in result.strategy_decisions:
            storage_locations.append(
                self._persist_model(store=store, category="decisions", model=decision)
            )
        for event in result.simulation_events:
            storage_locations.append(
                self._persist_model(store=store, category="events", model=event)
            )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="performance_summaries",
                model=result.performance_summary,
            )
        )
        for benchmark in result.benchmark_references:
            storage_locations.append(
                self._persist_model(store=store, category="benchmarks", model=benchmark)
            )
        storage_locations.append(
            self._persist_model(store=store, category="runs", model=result.backtest_run)
        )

        return RunBacktestWorkflowResponse(
            backtest_run=result.backtest_run,
            backtest_config=request.backtest_config,
            data_snapshots=result.data_snapshots,
            strategy_decisions=result.strategy_decisions,
            simulation_events=result.simulation_events,
            performance_summary=result.performance_summary,
            benchmark_references=result.benchmark_references,
            storage_locations=storage_locations,
            notes=[f"requested_by={request.requested_by}", *result.notes],
        )

    def _persist_model(
        self,
        *,
        store: LocalBacktestArtifactStore,
        category: str,
        model: StrictModel,
    ) -> ArtifactStorageLocation:
        """Persist one typed backtesting artifact."""

        artifact_id = _artifact_id(model=model)
        source_reference_ids = cast(_ProvenancedModel, model).provenance.source_reference_ids
        return store.persist_model(
            artifact_id=artifact_id,
            category=category,
            model=model,
            source_reference_ids=source_reference_ids,
        )


class _ProvenancedModel(Protocol):
    provenance: ProvenanceRecord


def _artifact_id(*, model: StrictModel) -> str:
    """Resolve the canonical identifier field for a strict model."""

    for field_name in type(model).model_fields:
        if field_name.endswith("_id") and field_name != "data_snapshot_id":
            value = getattr(model, field_name, None)
            if isinstance(value, str):
                return value
    if hasattr(model, "data_snapshot_id"):
        return cast(str, model.data_snapshot_id)
    raise ValueError(f"Could not resolve artifact ID for model type `{type(model).__name__}`.")
