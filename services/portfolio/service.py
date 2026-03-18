from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    PortfolioConstraint,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    RiskCheck,
    StrictModel,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.utils import make_prefixed_id
from services.portfolio.construction import (
    build_exposure_summary,
    build_portfolio_proposal,
    build_position_ideas,
    default_portfolio_constraints,
)
from services.portfolio.loaders import load_portfolio_inputs
from services.portfolio.storage import LocalPortfolioArtifactStore
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
    research_root: Path = Field(description="Root path containing persisted research artifacts.")
    ingestion_root: Path | None = Field(
        default=None,
        description="Optional ingestion artifact root used for company metadata and symbol resolution.",
    )
    backtesting_root: Path | None = Field(
        default=None,
        description="Optional backtesting artifact root used for contextual notes.",
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
    portfolio_proposal: PortfolioProposal = Field(
        description="Portfolio proposal created by the workflow."
    )
    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Explicit risk checks attached to the proposal.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Artifact storage locations written by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work, assumptions, or gating issues.",
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
            api_routes=["GET /portfolio-proposals"],
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
            company_id=request.company_id,
            as_of_time=request.as_of_time,
        )
        notes = [f"requested_by={request.requested_by}"]
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
        position_result = build_position_ideas(
            inputs=inputs,
            as_of_time=as_of_time,
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
        )
        position_ideas = position_result.position_ideas
        notes.extend(position_result.notes)

        constraints = request.constraints or default_portfolio_constraints(
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
        )
        exposure_summary = build_exposure_summary(
            position_ideas=position_ideas,
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
            summary_key=f"{inputs.company_id}:{as_of_time.isoformat()}",
        )
        proposal = build_portfolio_proposal(
            company_id=inputs.company_id,
            name=request.proposal_name or f"{inputs.company_id}_day7_portfolio_proposal",
            as_of_time=as_of_time,
            generated_at=self.clock.now(),
            target_nav_usd=request.target_nav_usd,
            position_ideas=position_ideas,
            constraints=constraints,
            exposure_summary=exposure_summary,
            clock=self.clock,
            workflow_run_id=portfolio_workflow_id,
        )

        signal_map = {signal.signal_id: signal for signal in inputs.signals}
        risk_service = RiskEngineService(clock=self.clock)
        risk_response = risk_service.evaluate(
            RiskEvaluationRequest(
                position_ideas=position_ideas,
                portfolio_proposal=proposal,
                constraints=constraints,
                signals_by_id=signal_map,
                evidence_assessments_by_id=inputs.evidence_assessments_by_id,
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

        output_root = request.output_root or (get_settings().resolved_artifact_root / "portfolio")
        store = LocalPortfolioArtifactStore(root=output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
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
            portfolio_proposal=proposal,
            risk_checks=risk_response.risk_checks,
            storage_locations=storage_locations,
            notes=notes,
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
