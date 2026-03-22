from __future__ import annotations

from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    Company,
    PortfolioAttribution,
    PortfolioProposal,
    PositionAttribution,
    ScenarioDefinition,
    Signal,
    StressTestResult,
    StressTestRun,
    StrictModel,
)
from libraries.utils import make_prefixed_id
from services.portfolio_analysis.attribution import (
    build_portfolio_attribution,
    build_position_attributions,
)
from services.portfolio_analysis.loaders import load_portfolio_analysis_inputs
from services.portfolio_analysis.storage import LocalPortfolioAnalysisArtifactStore
from services.portfolio_analysis.stress import build_scenario_definitions, run_stress_tests


class RunPortfolioAnalysisRequest(StrictModel):
    """Explicit local request to analyze one persisted portfolio proposal."""

    portfolio_root: Path = Field(description="Root path containing persisted portfolio artifacts.")
    signal_root: Path = Field(description="Root path containing persisted signal artifacts.")
    ingestion_root: Path | None = Field(
        default=None,
        description="Optional ingestion root used for resolved company metadata.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional portfolio-analysis artifact root.",
    )
    portfolio_proposal_id: str = Field(description="Portfolio proposal identifier to analyze.")
    requested_by: str = Field(description="Requester identifier.")


class RunPortfolioAnalysisResponse(StrictModel):
    """Result of the deterministic Day 20 portfolio-analysis workflow."""

    portfolio_attribution: PortfolioAttribution = Field(
        description="Proposal-level attribution artifact."
    )
    position_attributions: list[PositionAttribution] = Field(
        default_factory=list,
        description="Position-level attribution artifacts.",
    )
    scenario_definitions: list[ScenarioDefinition] = Field(
        default_factory=list,
        description="Persisted deterministic scenario definitions used in the run.",
    )
    stress_test_run: StressTestRun = Field(description="Stress-test batch run artifact.")
    stress_test_results: list[StressTestResult] = Field(
        default_factory=list,
        description="Structured stress-test results for the proposal.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing missing metadata or empty-proposal paths.",
    )


class PortfolioAnalysisService(BaseService):
    """Explain and stress test review-bound portfolio proposals deterministically."""

    capability_name = "portfolio_analysis"
    capability_description = (
        "Builds deterministic portfolio attribution and first-pass stress-testing artifacts."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PortfolioProposal", "PositionIdea", "Signal", "Company"],
            produces=[
                "PositionAttribution",
                "PortfolioAttribution",
                "ScenarioDefinition",
                "StressTestRun",
                "StressTestResult",
            ],
            api_routes=[],
        )

    def run_portfolio_analysis(
        self,
        request: RunPortfolioAnalysisRequest,
    ) -> RunPortfolioAnalysisResponse:
        """Load a persisted proposal and produce deterministic analysis artifacts."""

        inputs = load_portfolio_analysis_inputs(
            portfolio_root=request.portfolio_root,
            signal_root=request.signal_root,
            ingestion_root=request.ingestion_root,
            portfolio_proposal_id=request.portfolio_proposal_id,
        )
        return self.analyze_portfolio_proposal(
            portfolio_proposal=inputs.portfolio_proposal,
            signals_by_id=inputs.signals_by_id,
            companies_by_id=inputs.companies_by_id,
            output_root=request.output_root,
            requested_by=request.requested_by,
        )

    def analyze_portfolio_proposal(
        self,
        *,
        portfolio_proposal: PortfolioProposal,
        signals_by_id: dict[str, Signal],
        companies_by_id: dict[str, Company],
        output_root: Path | None,
        requested_by: str,
    ) -> RunPortfolioAnalysisResponse:
        """Analyze one in-memory proposal and persist attribution and stress artifacts."""

        workflow_run_id = make_prefixed_id("panalysis")
        resolved_output_root = output_root or (get_settings().resolved_artifact_root / "portfolio_analysis")
        notes = [f"requested_by={requested_by}"]
        if not portfolio_proposal.position_ideas:
            notes.append("Portfolio proposal contains no positions; attribution and stress artifacts reflect an empty proposal.")
        if not companies_by_id:
            notes.append("Normalized company metadata was unavailable; sector-aware attribution and stress scenarios remain conservative.")

        position_attributions = build_position_attributions(
            portfolio_proposal=portfolio_proposal,
            signals_by_id=signals_by_id,
            companies_by_id=companies_by_id,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
        )
        portfolio_attribution = build_portfolio_attribution(
            portfolio_proposal=portfolio_proposal,
            position_attributions=position_attributions,
            companies_by_id=companies_by_id,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
        )
        scenario_definitions = build_scenario_definitions(
            portfolio_proposal=portfolio_proposal,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
        )
        stress_test_run, stress_test_results = run_stress_tests(
            portfolio_proposal=portfolio_proposal,
            scenarios=scenario_definitions,
            companies_by_id=companies_by_id,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
        )

        store = LocalPortfolioAnalysisArtifactStore(root=resolved_output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
        for position_attribution in position_attributions:
            storage_locations.append(
                store.persist_model(
                    artifact_id=position_attribution.position_attribution_id,
                    category="position_attributions",
                    model=position_attribution,
                    source_reference_ids=position_attribution.provenance.source_reference_ids,
                )
            )
        storage_locations.append(
            store.persist_model(
                artifact_id=portfolio_attribution.portfolio_attribution_id,
                category="portfolio_attributions",
                model=portfolio_attribution,
                source_reference_ids=portfolio_attribution.provenance.source_reference_ids,
            )
        )
        for scenario_definition in scenario_definitions:
            storage_locations.append(
                store.persist_model(
                    artifact_id=scenario_definition.scenario_definition_id,
                    category="scenario_definitions",
                    model=scenario_definition,
                    source_reference_ids=scenario_definition.provenance.source_reference_ids,
                )
            )
        for stress_test_result in stress_test_results:
            storage_locations.append(
                store.persist_model(
                    artifact_id=stress_test_result.stress_test_result_id,
                    category="stress_test_results",
                    model=stress_test_result,
                    source_reference_ids=stress_test_result.provenance.source_reference_ids,
                )
            )
        storage_locations.append(
            store.persist_model(
                artifact_id=stress_test_run.stress_test_run_id,
                category="stress_test_runs",
                model=stress_test_run,
                source_reference_ids=stress_test_run.provenance.source_reference_ids,
            )
        )

        return RunPortfolioAnalysisResponse(
            portfolio_attribution=portfolio_attribution,
            position_attributions=position_attributions,
            scenario_definitions=scenario_definitions,
            stress_test_run=stress_test_run,
            stress_test_results=stress_test_results,
            storage_locations=storage_locations,
            notes=notes,
        )
