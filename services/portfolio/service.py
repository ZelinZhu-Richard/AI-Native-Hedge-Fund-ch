from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

from pydantic import Field

from libraries.config import get_settings
from libraries.core import resolve_artifact_workspace_from_stage_root
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    ConstraintResult,
    ConstraintSet,
    ConstructionDecision,
    PortfolioAttribution,
    PortfolioConstraint,
    PortfolioProposal,
    PortfolioProposalStatus,
    PortfolioSelectionSummary,
    PositionAttribution,
    PositionIdea,
    PositionSizingRationale,
    QualityDecision,
    RefusalReason,
    RiskCheck,
    ScenarioDefinition,
    SelectionConflict,
    SelectionRule,
    StressTestResult,
    StressTestRun,
    StrictModel,
    ValidationGate,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.utils import make_prefixed_id
from services.data_quality import DataQualityService
from services.portfolio.construction import (
    build_exposure_summary,
    build_portfolio_proposal,
    build_portfolio_selection,
    default_portfolio_constraints,
    make_portfolio_proposal_id,
)
from services.portfolio.loaders import load_portfolio_inputs
from services.portfolio.storage import LocalPortfolioArtifactStore
from services.portfolio_analysis import PortfolioAnalysisService
from services.risk_engine import RiskEngineService, RiskEvaluationRequest


class PortfolioConstructionRequest(StrictModel):
    """Request to assemble a paper portfolio proposal from explicit position ideas."""

    name: str = Field(description="Proposed portfolio name.")
    as_of_time: datetime = Field(description="UTC time the proposal should respect.")
    position_ideas: list[PositionIdea] = Field(description="Candidate position ideas.")
    constraints: list[PortfolioConstraint] = Field(
        default_factory=list, description="Constraints to apply."
    )
    requested_by: str = Field(description="Requester identifier.")


class PortfolioConstructionResponse(StrictModel):
    """Response returned after a portfolio proposal is assembled."""

    proposal: PortfolioProposal = Field(description="Constructed paper portfolio proposal.")


class RunPortfolioWorkflowRequest(StrictModel):
    """Explicit local request to build a Day 7 portfolio proposal from persisted artifacts."""

    signal_root: Path = Field(description="Root path containing persisted signal artifacts.")
    signal_arbitration_root: Path | None = Field(
        default=None,
        description="Optional root path containing persisted signal arbitration artifacts.",
    )
    research_root: Path = Field(description="Root path containing persisted research artifacts.")
    ingestion_root: Path | None = Field(
        default=None,
        description="Optional ingestion artifact root used for company metadata and symbol resolution.",
    )
    backtesting_root: Path | None = Field(
        default=None,
        description="Optional backtesting artifact root used for contextual notes.",
    )
    portfolio_analysis_root: Path | None = Field(
        default=None,
        description="Optional root path containing persisted portfolio-analysis artifacts.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional portfolio artifact root. Defaults to the configured artifact root.",
    )
    company_id: str | None = Field(
        default=None,
        description="Covered company identifier. Required when the signal root contains multiple companies.",
    )
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional signal cutoff. When omitted, latest-artifact loading is used for local development only.",
    )
    constraints: list[PortfolioConstraint] = Field(
        default_factory=list,
        description="Optional explicit constraints. Defaults are used when omitted.",
    )
    target_nav_usd: float = Field(
        default=1_000_000.0,
        gt=0.0,
        description="Target NAV used to size paper-trade notionals downstream.",
    )
    proposal_name: str | None = Field(
        default=None,
        description="Optional human-readable proposal name. Defaults to a company-scoped name.",
    )
    requested_by: str = Field(description="Requester identifier.")


class RunPortfolioWorkflowResponse(StrictModel):
    """Result of the deterministic Day 7 portfolio workflow."""

    portfolio_workflow_id: str = Field(description="Canonical workflow identifier.")
    company_id: str = Field(description="Covered company identifier.")
    position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Position ideas created from eligible signals.",
    )
    selection_rules: list[SelectionRule] = Field(
        default_factory=list,
        description="Deterministic selection rules used during portfolio construction.",
    )
    constraint_set: ConstraintSet | None = Field(
        default=None,
        description="Applied construction constraint set when available.",
    )
    constraint_results: list[ConstraintResult] = Field(
        default_factory=list,
        description="Explicit construction constraint results when available.",
    )
    position_sizing_rationales: list[PositionSizingRationale] = Field(
        default_factory=list,
        description="Sizing rationales for included positions when available.",
    )
    construction_decisions: list[ConstructionDecision] = Field(
        default_factory=list,
        description="Explicit include or reject decisions for candidate signals.",
    )
    selection_conflicts: list[SelectionConflict] = Field(
        default_factory=list,
        description="Selection conflicts recorded during portfolio construction.",
    )
    portfolio_selection_summary: PortfolioSelectionSummary | None = Field(
        default=None,
        description="Parent construction summary when portfolio selection artifacts were recorded.",
    )
    portfolio_proposal: PortfolioProposal = Field(
        description="Portfolio proposal created by the workflow."
    )
    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Explicit risk checks attached to the proposal.",
    )
    portfolio_attribution: PortfolioAttribution | None = Field(
        default=None,
        description="Proposal-level attribution artifact when portfolio analysis has run.",
    )
    position_attributions: list[PositionAttribution] = Field(
        default_factory=list,
        description="Position-level attribution artifacts when portfolio analysis has run.",
    )
    scenario_definitions: list[ScenarioDefinition] = Field(
        default_factory=list,
        description="Scenario definitions applied during portfolio analysis.",
    )
    stress_test_run: StressTestRun | None = Field(
        default=None,
        description="Stress-test batch run artifact when portfolio analysis has run.",
    )
    stress_test_results: list[StressTestResult] = Field(
        default_factory=list,
        description="Stress-test results generated during portfolio analysis.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work, assumptions, or gating issues.",
    )
    validation_gate: ValidationGate | None = Field(
        default=None,
        description="Data-quality gate recorded for the portfolio workflow when validation ran.",
    )
    quality_decision: QualityDecision | None = Field(
        default=None,
        description="Overall decision emitted by the portfolio validation gate.",
    )
    refusal_reason: RefusalReason | None = Field(
        default=None,
        description="Primary refusal reason when portfolio proposal generation was blocked.",
    )


class PortfolioConstructionService(BaseService):
    """Build reviewable portfolio proposals from persisted signals and research artifacts."""

    capability_name = "portfolio"
    capability_description = "Constructs risk-annotated paper portfolio proposals from signal-backed ideas."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Signal", "ResearchBrief", "EvidenceAssessment", "PortfolioConstraint"],
            produces=["PositionIdea", "PortfolioProposal", "RiskCheck"],
            api_routes=["GET /portfolio/proposals"],
        )

    def construct(self, request: PortfolioConstructionRequest) -> PortfolioConstructionResponse:
        """Build a portfolio proposal from already constructed position ideas."""

        now = self.clock.now()
        workflow_run_id = make_prefixed_id("pflow")
        constraints = request.constraints or default_portfolio_constraints(
            clock=self.clock, workflow_run_id=workflow_run_id
        )
        exposure_summary = build_exposure_summary(
            position_ideas=request.position_ideas,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
            summary_key=f"{request.name}:{request.as_of_time.isoformat()}",
        )
        proposal = build_portfolio_proposal(
            company_id=request.position_ideas[0].company_id if request.position_ideas else "co_unknown",
            name=request.name,
            as_of_time=request.as_of_time,
            generated_at=now,
            target_nav_usd=1_000_000.0,
            position_ideas=request.position_ideas,
            constraints=constraints,
            exposure_summary=exposure_summary,
            signal_bundle_id=None,
            arbitration_decision_id=None,
            portfolio_attribution_id=None,
            stress_test_run_id=None,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
        ).model_copy(
            update={
                "status": PortfolioProposalStatus.DRAFT,
                "updated_at": now,
            }
        )
        return PortfolioConstructionResponse(proposal=proposal)

    def run_portfolio_workflow(
        self,
        request: RunPortfolioWorkflowRequest,
    ) -> RunPortfolioWorkflowResponse:
        """Execute the deterministic Day 7 signal-to-proposal workflow."""

        portfolio_workflow_id = make_prefixed_id("pflow")
        inputs = load_portfolio_inputs(
            signal_root=request.signal_root,
            research_root=request.research_root,
            ingestion_root=request.ingestion_root,
            backtesting_root=request.backtesting_root,
            signal_arbitration_root=request.signal_arbitration_root,
            company_id=request.company_id,
            as_of_time=request.as_of_time,
        )
        notes = [f"requested_by={request.requested_by}"]
        notes.extend(inputs.notes)
        if request.as_of_time is None:
            notes.append(
                "No as_of_time provided; latest-artifact loading is a local-development convenience and not replay-safe."
            )
        else:
            notes.append(f"as_of_time={request.as_of_time.isoformat()}")
        if inputs.latest_backtest_run is not None:
            notes.append(
                "latest_backtest_run="
                f"{inputs.latest_backtest_run.backtest_run_id}"
                f"(exploratory_only={inputs.latest_backtest_run.exploratory_only})"
            )

        as_of_time = request.as_of_time or (
            max(signal.effective_at for signal in inputs.signals)
            if inputs.signals
            else self.clock.now()
        )
        constraints = request.constraints or default_portfolio_constraints(
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
        )
        proposal_name = request.proposal_name or f"{inputs.company_id}_day7_portfolio_proposal"
        proposal_id = make_portfolio_proposal_id(
            company_id=inputs.company_id,
            name=proposal_name,
            as_of_time=as_of_time,
        )
        selection_result = build_portfolio_selection(
            inputs=inputs,
            proposal_id=proposal_id,
            constraints=constraints,
            as_of_time=as_of_time,
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
        )
        position_ideas = selection_result.position_ideas
        notes.extend(selection_result.notes)
        exposure_summary = build_exposure_summary(
            position_ideas=position_ideas,
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
            summary_key=f"{inputs.company_id}:{as_of_time.isoformat()}",
        )
        proposal = build_portfolio_proposal(
            company_id=inputs.company_id,
            name=proposal_name,
            as_of_time=as_of_time,
            generated_at=self.clock.now(),
            target_nav_usd=request.target_nav_usd,
            position_ideas=position_ideas,
            constraints=constraints,
            exposure_summary=exposure_summary,
            signal_bundle_id=(
                inputs.signal_bundle.signal_bundle_id if inputs.signal_bundle is not None else None
            ),
            arbitration_decision_id=(
                inputs.arbitration_decision.arbitration_decision_id
                if inputs.arbitration_decision is not None
                else None
            ),
            portfolio_attribution_id=None,
            stress_test_run_id=None,
            portfolio_selection_summary_id=selection_result.portfolio_selection_summary.portfolio_selection_summary_id,
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
        )

        output_root = request.output_root or (get_settings().resolved_artifact_root / "portfolio")
        signal_map = {signal.signal_id: signal for signal in inputs.signals}
        proposal_source_reference_ids = sorted(
            {
                *proposal.provenance.source_reference_ids,
                *(
                    source_reference_id
                    for signal in inputs.signals
                    for source_reference_id in signal.provenance.source_reference_ids
                ),
                *(
                    source_reference_id
                    for idea in position_ideas
                    for source_reference_id in idea.provenance.source_reference_ids
                ),
            }
        )
        proposal_upstream_artifact_ids = [
            exposure_summary.portfolio_exposure_summary_id,
            selection_result.constraint_set.constraint_set_id,
            selection_result.portfolio_selection_summary.portfolio_selection_summary_id,
            *[idea.position_idea_id for idea in position_ideas],
            *[
                rationale.position_sizing_rationale_id
                for rationale in selection_result.position_sizing_rationales
            ],
            *[
                decision.construction_decision_id
                for decision in selection_result.construction_decisions
            ],
            *[
                result.constraint_result_id for result in selection_result.constraint_results
            ],
            *[
                conflict.selection_conflict_id for conflict in selection_result.selection_conflicts
            ],
            *[signal.signal_id for signal in inputs.signals],
            *(
                [inputs.signal_bundle.signal_bundle_id]
                if inputs.signal_bundle is not None
                else []
            ),
            *(
                [inputs.arbitration_decision.arbitration_decision_id]
                if inputs.arbitration_decision is not None
                else []
            ),
            *proposal.provenance.upstream_artifact_ids,
        ]
        proposal = proposal.model_copy(
            update={
                "provenance": proposal.provenance.model_copy(
                    update={
                        "source_reference_ids": proposal_source_reference_ids,
                        "upstream_artifact_ids": sorted(
                            {artifact_id for artifact_id in proposal_upstream_artifact_ids if artifact_id}
                        ),
                    }
                )
            }
        )
        portfolio_workspace = resolve_artifact_workspace_from_stage_root(output_root)
        quality_root = portfolio_workspace.data_quality_root
        portfolio_analysis_root = (
            request.portfolio_analysis_root or portfolio_workspace.portfolio_analysis_root
        )
        validation_result = DataQualityService(clock=self.clock).validate_portfolio_proposal(
            company_id=inputs.company_id,
            signals_by_id=signal_map,
            position_ideas=position_ideas,
            portfolio_proposal=proposal,
            workflow_run_id=portfolio_workflow_id,
            requested_by=request.requested_by,
            output_root=quality_root,
        )
        analysis_response = PortfolioAnalysisService(clock=self.clock).analyze_portfolio_proposal(
            portfolio_proposal=proposal,
            signals_by_id=signal_map,
            companies_by_id=(
                {inputs.company.company_id: inputs.company}
                if inputs.company is not None
                else {}
            ),
            constraint_set=selection_result.constraint_set,
            constraint_results=selection_result.constraint_results,
            position_sizing_rationales=selection_result.position_sizing_rationales,
            construction_decisions=selection_result.construction_decisions,
            portfolio_selection_summary=selection_result.portfolio_selection_summary,
            output_root=portfolio_analysis_root,
            requested_by=request.requested_by,
        )
        notes.extend(analysis_response.notes)
        proposal = proposal.model_copy(
            update={
                "portfolio_attribution_id": analysis_response.portfolio_attribution.portfolio_attribution_id,
                "stress_test_run_id": analysis_response.stress_test_run.stress_test_run_id,
            }
        )
        risk_service = RiskEngineService(clock=self.clock)
        risk_response = risk_service.evaluate(
            RiskEvaluationRequest(
                position_ideas=position_ideas,
                portfolio_proposal=proposal,
                constraints=constraints,
                signals_by_id=signal_map,
                evidence_assessments_by_id=inputs.evidence_assessments_by_id,
                signal_bundle=inputs.signal_bundle,
                arbitration_decision=inputs.arbitration_decision,
                signal_conflicts=inputs.signal_conflicts,
                constraint_set=selection_result.constraint_set,
                constraint_results=selection_result.constraint_results,
                position_sizing_rationales=selection_result.position_sizing_rationales,
                construction_decisions=selection_result.construction_decisions,
                selection_conflicts=selection_result.selection_conflicts,
                portfolio_selection_summary=selection_result.portfolio_selection_summary,
                portfolio_attribution=analysis_response.portfolio_attribution,
                stress_test_run=analysis_response.stress_test_run,
                stress_test_results=analysis_response.stress_test_results,
                requested_by=request.requested_by,
            )
        )
        proposal = proposal.model_copy(
            update={
                "risk_checks": risk_response.risk_checks,
                "blocking_issues": risk_response.blocking_issues,
                "updated_at": risk_response.evaluated_at,
            }
        )
        notes.extend(risk_response.blocking_issues)

        store = LocalPortfolioArtifactStore(root=output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = [
            *validation_result.storage_locations,
            *analysis_response.storage_locations,
        ]
        for selection_rule in selection_result.selection_rules:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="selection_rules",
                    model=selection_rule,
                )
            )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="constraint_sets",
                model=selection_result.constraint_set,
            )
        )
        for constraint_result in selection_result.constraint_results:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="constraint_results",
                    model=constraint_result,
                )
            )
        for rationale in selection_result.position_sizing_rationales:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="position_sizing_rationales",
                    model=rationale,
                )
            )
        for decision in selection_result.construction_decisions:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="construction_decisions",
                    model=decision,
                )
            )
        for conflict in selection_result.selection_conflicts:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="selection_conflicts",
                    model=conflict,
                )
            )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="portfolio_selection_summaries",
                model=selection_result.portfolio_selection_summary,
            )
        )
        for constraint in constraints:
            storage_locations.append(
                self._persist_model(store=store, category="constraints", model=constraint)
            )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="exposure_summaries",
                model=exposure_summary,
            )
        )
        for position_idea in position_ideas:
            storage_locations.append(
                self._persist_model(
                    store=store,
                    category="position_ideas",
                    model=position_idea,
                )
            )
        for risk_check in risk_response.risk_checks:
            storage_locations.append(
                self._persist_model(store=store, category="risk_checks", model=risk_check)
            )
        storage_locations.append(
            self._persist_model(
                store=store,
                category="portfolio_proposals",
                model=proposal,
            )
        )

        return RunPortfolioWorkflowResponse(
            portfolio_workflow_id=portfolio_workflow_id,
            company_id=inputs.company_id,
            position_ideas=position_ideas,
            selection_rules=selection_result.selection_rules,
            constraint_set=selection_result.constraint_set,
            constraint_results=selection_result.constraint_results,
            position_sizing_rationales=selection_result.position_sizing_rationales,
            construction_decisions=selection_result.construction_decisions,
            selection_conflicts=selection_result.selection_conflicts,
            portfolio_selection_summary=selection_result.portfolio_selection_summary,
            portfolio_proposal=proposal,
            risk_checks=risk_response.risk_checks,
            portfolio_attribution=analysis_response.portfolio_attribution,
            position_attributions=analysis_response.position_attributions,
            scenario_definitions=analysis_response.scenario_definitions,
            stress_test_run=analysis_response.stress_test_run,
            stress_test_results=analysis_response.stress_test_results,
            storage_locations=storage_locations,
            notes=notes,
            validation_gate=validation_result.validation_gate,
            quality_decision=validation_result.validation_gate.decision,
            refusal_reason=validation_result.validation_gate.refusal_reason,
        )

    def _persist_model(
        self,
        *,
        store: LocalPortfolioArtifactStore,
        category: str,
        model: StrictModel,
    ) -> ArtifactStorageLocation:
        """Persist one typed portfolio artifact."""

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
        if field_name.endswith("_id"):
            value = getattr(model, field_name, None)
            if isinstance(value, str):
                return value
    raise ValueError(f"Could not resolve artifact ID for model type `{type(model).__name__}`.")
