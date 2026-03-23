from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AlertRecord,
    ArtifactStorageLocation,
    DailyPaperSummary,
    DailySystemReport,
    Experiment,
    ExperimentMetric,
    ExperimentScorecard,
    FailureCase,
    PaperTrade,
    PortfolioAttribution,
    PortfolioProposal,
    PortfolioSelectionSummary,
    ProposalScorecard,
    RealismWarning,
    ReconciliationReport,
    ReportingContext,
    ResearchBrief,
    ResearchSummary,
    ReviewFollowup,
    ReviewQueueItem,
    ReviewQueueSummary,
    RiskCheck,
    RiskSummary,
    RobustnessCheck,
    RunSummary,
    ServiceStatus,
    StressTestResult,
    StressTestRun,
    StrictModel,
    SystemCapabilitySummary,
    ValidationGate,
)
from libraries.schemas.portfolio_construction import ConstructionDecision, PositionSizingRationale
from libraries.schemas.research import (
    CounterHypothesis,
    EvaluationReport,
    EvidenceAssessment,
    Hypothesis,
)
from libraries.utils import make_prefixed_id
from services.reporting.builders import (
    build_daily_system_report,
    build_experiment_scorecard,
    build_proposal_scorecard,
    build_research_summary,
    build_review_queue_summary,
    build_risk_summary,
    build_system_capability_summary,
)
from services.reporting.storage import LocalReportingArtifactStore


class GenerateResearchSummaryRequest(StrictModel):
    """Request to build one grounded research summary."""

    research_brief: ResearchBrief = Field(description="Research brief to summarize.")
    hypothesis: Hypothesis | None = Field(default=None)
    counter_hypothesis: CounterHypothesis | None = Field(default=None)
    evidence_assessment: EvidenceAssessment | None = Field(default=None)
    validation_gates: list[ValidationGate] = Field(default_factory=list)
    requested_by: str = Field(description="Requester identifier.")


class GenerateResearchSummaryResponse(StrictModel):
    """Generated research summary plus grounding context."""

    research_summary: ResearchSummary = Field(description="Persisted grounded research summary.")
    reporting_context: ReportingContext = Field(
        description="Derived context explaining how the summary was built."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GenerateRiskSummaryRequest(StrictModel):
    """Request to build one grounded risk summary."""

    portfolio_proposal: PortfolioProposal = Field(description="Portfolio proposal to summarize.")
    risk_checks: list[RiskCheck] = Field(default_factory=list)
    stress_test_results: list[StressTestResult] = Field(default_factory=list)
    validation_gates: list[ValidationGate] = Field(default_factory=list)
    reconciliation_report: ReconciliationReport | None = Field(default=None)
    requested_by: str = Field(description="Requester identifier.")


class GenerateRiskSummaryResponse(StrictModel):
    """Generated risk summary plus grounding context."""

    risk_summary: RiskSummary = Field(description="Persisted grounded risk summary.")
    reporting_context: ReportingContext = Field(
        description="Derived context explaining how the summary was built."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GenerateReviewQueueSummaryRequest(StrictModel):
    """Request to build one grounded review-queue summary."""

    queue_items: list[ReviewQueueItem] = Field(default_factory=list)
    requested_by: str = Field(description="Requester identifier.")


class GenerateReviewQueueSummaryResponse(StrictModel):
    """Generated review-queue summary plus grounding context."""

    review_queue_summary: ReviewQueueSummary = Field(
        description="Persisted grounded review-queue summary."
    )
    reporting_context: ReportingContext = Field(
        description="Derived context explaining how the summary was built."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GenerateExperimentScorecardRequest(StrictModel):
    """Request to build one grounded experiment scorecard."""

    experiment: Experiment = Field(description="Experiment to summarize.")
    evaluation_report: EvaluationReport | None = Field(default=None)
    experiment_metrics: list[ExperimentMetric] = Field(default_factory=list)
    failure_cases: list[FailureCase] = Field(default_factory=list)
    robustness_checks: list[RobustnessCheck] = Field(default_factory=list)
    realism_warnings: list[RealismWarning] = Field(default_factory=list)
    validation_gates: list[ValidationGate] = Field(default_factory=list)
    requested_by: str = Field(description="Requester identifier.")


class GenerateExperimentScorecardResponse(StrictModel):
    """Generated experiment scorecard plus grounding context."""

    experiment_scorecard: ExperimentScorecard = Field(
        description="Persisted grounded experiment scorecard."
    )
    reporting_context: ReportingContext = Field(
        description="Derived context explaining how the scorecard was built."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GenerateProposalScorecardRequest(StrictModel):
    """Request to build one grounded proposal scorecard."""

    portfolio_proposal: PortfolioProposal = Field(description="Portfolio proposal to summarize.")
    portfolio_selection_summary: PortfolioSelectionSummary | None = Field(default=None)
    construction_decisions: list[ConstructionDecision] = Field(default_factory=list)
    position_sizing_rationales: list[PositionSizingRationale] = Field(default_factory=list)
    portfolio_attribution: PortfolioAttribution | None = Field(default=None)
    stress_test_run: StressTestRun | None = Field(default=None)
    stress_test_results: list[StressTestResult] = Field(default_factory=list)
    risk_checks: list[RiskCheck] = Field(default_factory=list)
    validation_gates: list[ValidationGate] = Field(default_factory=list)
    reconciliation_report: ReconciliationReport | None = Field(default=None)
    realism_warnings: list[RealismWarning] = Field(default_factory=list)
    paper_trades: list[PaperTrade] = Field(default_factory=list)
    requested_by: str = Field(description="Requester identifier.")


class GenerateProposalScorecardResponse(StrictModel):
    """Generated proposal scorecard plus grounding context."""

    proposal_scorecard: ProposalScorecard = Field(
        description="Persisted grounded proposal scorecard."
    )
    reporting_context: ReportingContext = Field(
        description="Derived context explaining how the scorecard was built."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GenerateDailySystemReportRequest(StrictModel):
    """Request to build one grounded daily system report."""

    report_date: date = Field(description="Date summarized by the report.")
    run_summaries: list[RunSummary] = Field(default_factory=list)
    alert_records: list[AlertRecord] = Field(default_factory=list)
    service_statuses: list[ServiceStatus] = Field(default_factory=list)
    review_queue_summary: ReviewQueueSummary | None = Field(default=None)
    daily_paper_summaries: list[DailyPaperSummary] = Field(default_factory=list)
    review_followups: list[ReviewFollowup] = Field(default_factory=list)
    proposal_scorecards: list[ProposalScorecard] = Field(default_factory=list)
    experiment_scorecards: list[ExperimentScorecard] = Field(default_factory=list)
    requested_by: str = Field(description="Requester identifier.")


class GenerateDailySystemReportResponse(StrictModel):
    """Generated daily system report plus grounding context."""

    daily_system_report: DailySystemReport = Field(
        description="Persisted grounded daily system report."
    )
    reporting_context: ReportingContext = Field(
        description="Derived context explaining how the report was built."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GenerateSystemCapabilitySummaryRequest(StrictModel):
    """Request to build one grounded system capability summary."""

    capability_name: str = Field(description="Capability or subsystem name.")
    service_names: list[str] = Field(default_factory=list)
    recent_run_summaries: list[RunSummary] = Field(default_factory=list)
    alert_records: list[AlertRecord] = Field(default_factory=list)
    evidence_artifact_ids: list[str] = Field(default_factory=list)
    current_limitations: list[str] = Field(default_factory=list)
    maturity_notes: list[str] = Field(default_factory=list)
    requested_by: str = Field(description="Requester identifier.")


class GenerateSystemCapabilitySummaryResponse(StrictModel):
    """Generated system capability summary plus grounding context."""

    system_capability_summary: SystemCapabilitySummary = Field(
        description="Persisted grounded capability summary."
    )
    reporting_context: ReportingContext = Field(
        description="Derived context explaining how the summary was built."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReportingService(BaseService):
    """Generate deterministic summary artifacts without replacing source truth."""

    capability_name = "reporting"
    capability_description = (
        "Generates deterministic, artifact-backed summaries and scorecards for operators, researchers, and reviewers."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=[
                "research artifacts",
                "portfolio proposals",
                "evaluation artifacts",
                "monitoring summaries",
                "review queue items",
            ],
            produces=[
                "ResearchSummary",
                "RiskSummary",
                "ReviewQueueSummary",
                "ExperimentScorecard",
                "ProposalScorecard",
                "DailySystemReport",
                "SystemCapabilitySummary",
            ],
            api_routes=[
                "GET /reports/daily-system/latest",
                "GET /reports/proposals/{portfolio_proposal_id}/scorecard",
                "GET /reports/review-queue/latest",
            ],
        )

    def generate_research_summary(
        self,
        request: GenerateResearchSummaryRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateResearchSummaryResponse:
        """Build and persist one grounded research summary."""

        report, context, notes = build_research_summary(
            research_summary_id=make_prefixed_id("rsum"),
            research_brief=request.research_brief,
            hypothesis=request.hypothesis,
            counter_hypothesis=request.counter_hypothesis,
            evidence_assessment=request.evidence_assessment,
            validation_gates=request.validation_gates,
            clock=self.clock,
            requested_by=request.requested_by,
        )
        storage = self._persist(output_root=output_root, category="research_summaries", model=report)
        return GenerateResearchSummaryResponse(
            research_summary=report,
            reporting_context=context,
            storage_locations=[storage],
            notes=notes,
        )

    def generate_risk_summary(
        self,
        request: GenerateRiskSummaryRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateRiskSummaryResponse:
        """Build and persist one grounded risk summary."""

        report, context, notes = build_risk_summary(
            risk_summary_id=make_prefixed_id("risksum"),
            portfolio_proposal=request.portfolio_proposal,
            risk_checks=request.risk_checks,
            stress_test_results=request.stress_test_results,
            validation_gates=request.validation_gates,
            reconciliation_report=request.reconciliation_report,
            clock=self.clock,
            requested_by=request.requested_by,
        )
        storage = self._persist(output_root=output_root, category="risk_summaries", model=report)
        return GenerateRiskSummaryResponse(
            risk_summary=report,
            reporting_context=context,
            storage_locations=[storage],
            notes=notes,
        )

    def generate_review_queue_summary(
        self,
        request: GenerateReviewQueueSummaryRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateReviewQueueSummaryResponse:
        """Build and persist one grounded review-queue summary."""

        report, context, notes = build_review_queue_summary(
            review_queue_summary_id=make_prefixed_id("rqsum"),
            queue_items=request.queue_items,
            clock=self.clock,
            requested_by=request.requested_by,
        )
        storage = self._persist(
            output_root=output_root,
            category="review_queue_summaries",
            model=report,
        )
        return GenerateReviewQueueSummaryResponse(
            review_queue_summary=report,
            reporting_context=context,
            storage_locations=[storage],
            notes=notes,
        )

    def generate_experiment_scorecard(
        self,
        request: GenerateExperimentScorecardRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateExperimentScorecardResponse:
        """Build and persist one grounded experiment scorecard."""

        report, context, notes = build_experiment_scorecard(
            experiment_scorecard_id=make_prefixed_id("expsc"),
            experiment=request.experiment,
            evaluation_report=request.evaluation_report,
            experiment_metrics=request.experiment_metrics,
            failure_cases=request.failure_cases,
            robustness_checks=request.robustness_checks,
            realism_warnings=request.realism_warnings,
            validation_gates=request.validation_gates,
            clock=self.clock,
            requested_by=request.requested_by,
        )
        storage = self._persist(
            output_root=output_root,
            category="experiment_scorecards",
            model=report,
        )
        return GenerateExperimentScorecardResponse(
            experiment_scorecard=report,
            reporting_context=context,
            storage_locations=[storage],
            notes=notes,
        )

    def generate_proposal_scorecard(
        self,
        request: GenerateProposalScorecardRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateProposalScorecardResponse:
        """Build and persist one grounded proposal scorecard."""

        report, context, notes = build_proposal_scorecard(
            proposal_scorecard_id=make_prefixed_id("propsc"),
            portfolio_proposal=request.portfolio_proposal,
            portfolio_selection_summary=request.portfolio_selection_summary,
            construction_decisions=request.construction_decisions,
            position_sizing_rationales=request.position_sizing_rationales,
            portfolio_attribution=request.portfolio_attribution,
            stress_test_run=request.stress_test_run,
            stress_test_results=request.stress_test_results,
            risk_checks=request.risk_checks,
            validation_gates=request.validation_gates,
            reconciliation_report=request.reconciliation_report,
            realism_warnings=request.realism_warnings,
            paper_trades=request.paper_trades,
            clock=self.clock,
            requested_by=request.requested_by,
        )
        storage = self._persist(
            output_root=output_root,
            category="proposal_scorecards",
            model=report,
        )
        return GenerateProposalScorecardResponse(
            proposal_scorecard=report,
            reporting_context=context,
            storage_locations=[storage],
            notes=notes,
        )

    def generate_daily_system_report(
        self,
        request: GenerateDailySystemReportRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateDailySystemReportResponse:
        """Build and persist one grounded daily system report."""

        report, context, notes = build_daily_system_report(
            daily_system_report_id=make_prefixed_id("dsrpt"),
            report_date=request.report_date,
            run_summaries=request.run_summaries,
            alert_records=request.alert_records,
            service_statuses=request.service_statuses,
            review_queue_summary=request.review_queue_summary,
            daily_paper_summaries=request.daily_paper_summaries,
            review_followups=request.review_followups,
            proposal_scorecards=request.proposal_scorecards,
            experiment_scorecards=request.experiment_scorecards,
            clock=self.clock,
            requested_by=request.requested_by,
        )
        storage = self._persist(
            output_root=output_root,
            category="daily_system_reports",
            model=report,
        )
        return GenerateDailySystemReportResponse(
            daily_system_report=report,
            reporting_context=context,
            storage_locations=[storage],
            notes=notes,
        )

    def generate_system_capability_summary(
        self,
        request: GenerateSystemCapabilitySummaryRequest,
        *,
        output_root: Path | None = None,
    ) -> GenerateSystemCapabilitySummaryResponse:
        """Build and persist one grounded system capability summary."""

        report, context, notes = build_system_capability_summary(
            system_capability_summary_id=make_prefixed_id("capsum"),
            capability_name=request.capability_name,
            service_names=request.service_names,
            recent_run_summaries=request.recent_run_summaries,
            alert_records=request.alert_records,
            evidence_artifact_ids=request.evidence_artifact_ids,
            current_limitations=request.current_limitations,
            maturity_notes=request.maturity_notes,
            clock=self.clock,
            requested_by=request.requested_by,
        )
        storage = self._persist(
            output_root=output_root,
            category="system_capability_summaries",
            model=report,
        )
        return GenerateSystemCapabilitySummaryResponse(
            system_capability_summary=report,
            reporting_context=context,
            storage_locations=[storage],
            notes=notes,
        )

    def _persist(
        self,
        *,
        output_root: Path | None,
        category: str,
        model: StrictModel,
    ) -> ArtifactStorageLocation:
        """Persist one reporting artifact."""

        artifact_id = _artifact_id(model)
        store = LocalReportingArtifactStore(
            root=output_root or (get_settings().resolved_artifact_root / "reporting"),
            clock=self.clock,
        )
        provenance = getattr(model, "provenance", None)
        source_reference_ids = provenance.source_reference_ids if provenance is not None else []
        return store.persist_model(
            artifact_id=artifact_id,
            category=category,
            model=model,
            source_reference_ids=source_reference_ids,
        )


def _artifact_id(model: StrictModel) -> str:
    for field_name in type(model).model_fields:
        if field_name.endswith("_id"):
            value = getattr(model, field_name, None)
            if isinstance(value, str):
                return value
    raise ValueError(f"Could not resolve artifact ID for `{type(model).__name__}`.")
