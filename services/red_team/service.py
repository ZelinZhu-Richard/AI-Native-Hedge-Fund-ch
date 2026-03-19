from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    AlertRecord,
    ArtifactStorageLocation,
    AuditLog,
    AuditOutcome,
    EvidenceAssessment,
    Experiment,
    ExtractedClaim,
    GuardrailViolation,
    PaperTrade,
    ParsedDocumentText,
    PipelineEventType,
    PortfolioProposal,
    RedTeamCase,
    ResearchBrief,
    ReviewDecision,
    RunSummary,
    SafetyFinding,
    Severity,
    Signal,
    StrictModel,
    WorkflowStatus,
)
from libraries.utils import make_prefixed_id
from services.audit import AuditEventRequest, AuditLoggingService
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordPipelineEventResponse,
    RecordRunSummaryRequest,
)
from services.red_team.checks import (
    DEFAULT_SCENARIO_NAMES,
    LoadedRedTeamWorkspace,
    execute_red_team_scenario,
)
from services.red_team.storage import LocalRedTeamArtifactStore, load_models


class RunRedTeamSuiteRequest(StrictModel):
    """Request to execute the deterministic red-team suite against persisted artifacts."""

    parsing_root: Path | None = Field(default=None)
    research_root: Path | None = Field(default=None)
    signal_root: Path | None = Field(default=None)
    portfolio_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    evaluation_root: Path | None = Field(default=None)
    experiment_root: Path | None = Field(default=None)
    output_root: Path | None = Field(default=None)
    monitoring_root: Path | None = Field(default=None)
    audit_root: Path | None = Field(default=None)
    scenario_names: list[str] = Field(
        default_factory=list,
        description="Optional subset of scenario names to execute.",
    )
    requested_by: str = Field(description="Requester or workflow owner.")


class RunRedTeamSuiteResponse(StrictModel):
    """Persisted outputs returned after executing the red-team suite."""

    red_team_cases: list[RedTeamCase] = Field(default_factory=list)
    guardrail_violations: list[GuardrailViolation] = Field(default_factory=list)
    safety_findings: list[SafetyFinding] = Field(default_factory=list)
    run_summary: RunSummary | None = Field(
        default=None,
        description="Monitoring run summary for the suite run when monitoring is enabled.",
    )
    alert_records: list[AlertRecord] = Field(
        default_factory=list,
        description="Alerts emitted by monitoring for the suite run.",
    )
    audit_log: AuditLog | None = Field(
        default=None,
        description="Audit log emitted for suite completion.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RedTeamService(BaseService):
    """Execute deterministic adversarial checks against cloned repository artifacts."""

    capability_name = "red_team"
    capability_description = (
        "Runs adversarial guardrail checks and records structured failures, alerts, and audit events."
    )

    def capability(self) -> ServiceCapability:
        """Return service metadata for discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=[
                "ResearchBrief",
                "Signal",
                "PortfolioProposal",
                "PaperTrade",
                "Experiment",
                "evaluation artifacts",
            ],
            produces=["RedTeamCase", "GuardrailViolation", "SafetyFinding", "RunSummary"],
            api_routes=[],
        )

    def run_red_team_suite(self, request: RunRedTeamSuiteRequest) -> RunRedTeamSuiteResponse:
        """Execute the configured adversarial scenarios and persist structured outputs."""

        red_team_root, monitoring_root, audit_root = self._resolve_roots(request)
        monitoring_service = MonitoringService(clock=self.clock)
        run_id = make_prefixed_id("rtsuite")
        started_at = self.clock.now()
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="red_team_suite",
                workflow_run_id=run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message="Red-team suite started.",
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )

        try:
            response = self._run_red_team_suite_impl(
                request=request,
                run_id=run_id,
                red_team_root=red_team_root,
                monitoring_root=monitoring_root,
                audit_root=audit_root,
                started_at=started_at,
                start_event=start_event,
            )
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="red_team_suite",
                    workflow_run_id=run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=f"Red-team suite failed: {exc}",
                    related_artifact_ids=[run_id],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="red_team_suite",
                    workflow_run_id=run_id,
                    service_name=self.capability_name,
                    requested_by=request.requested_by,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=["Red-team suite terminated before completing all scenarios."],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise
        return response

    def _run_red_team_suite_impl(
        self,
        *,
        request: RunRedTeamSuiteRequest,
        run_id: str,
        red_team_root: Path,
        monitoring_root: Path,
        audit_root: Path,
        started_at: datetime,
        start_event: RecordPipelineEventResponse,
    ) -> RunRedTeamSuiteResponse:
        """Run the deterministic suite once roots and monitoring are initialized."""

        workspace = self._load_workspace(request)
        store = LocalRedTeamArtifactStore(root=red_team_root, clock=self.clock)
        scenario_names = list(dict.fromkeys(request.scenario_names or list(DEFAULT_SCENARIO_NAMES)))
        notes = [
            "Day 13 red-team outputs are deterministic structural checks, not proof of production correctness.",
            "Adversarial scenarios execute against cloned in-memory artifacts only.",
        ]
        cases: list[RedTeamCase] = []
        violations: list[GuardrailViolation] = []
        findings: list[SafetyFinding] = []
        storage_locations: list[ArtifactStorageLocation] = []

        for scenario_name in scenario_names:
            scenario = execute_red_team_scenario(
                scenario_name=scenario_name,
                workspace=workspace,
                clock=self.clock,
                workflow_run_id=run_id,
            )
            if scenario is None:
                notes.append(f"Skipped `{scenario_name}` because no compatible persisted target was available.")
                continue
            cases.append(scenario.red_team_case)
            violations.extend(scenario.guardrail_violations)
            findings.extend(scenario.safety_findings)
            notes.extend(scenario.notes)
            for violation in scenario.guardrail_violations:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=violation.guardrail_violation_id,
                        category="guardrail_violations",
                        model=violation,
                        source_reference_ids=violation.provenance.source_reference_ids,
                    )
                )
            for finding in scenario.safety_findings:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=finding.safety_finding_id,
                        category="safety_findings",
                        model=finding,
                        source_reference_ids=finding.provenance.source_reference_ids,
                    )
                )
            storage_locations.append(
                store.persist_model(
                    artifact_id=scenario.red_team_case.red_team_case_id,
                    category="cases",
                    model=scenario.red_team_case,
                    source_reference_ids=scenario.red_team_case.provenance.source_reference_ids,
                )
            )

        workflow_status = self._workflow_status(violations=violations)
        storage_locations.append(start_event.storage_location)
        completed_event = MonitoringService(clock=self.clock).record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="red_team_suite",
                workflow_run_id=run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_COMPLETED,
                status=workflow_status,
                message=(
                    f"Red-team suite completed with {len(cases)} cases and {len(violations)} guardrail violations."
                ),
                related_artifact_ids=[
                    *[case.red_team_case_id for case in cases],
                    *[violation.guardrail_violation_id for violation in violations],
                    *[finding.safety_finding_id for finding in findings],
                ],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=monitoring_root,
        )
        storage_locations.append(completed_event.storage_location)
        pipeline_event_ids = [
            start_event.pipeline_event.pipeline_event_id,
            completed_event.pipeline_event.pipeline_event_id,
        ]
        if workflow_status is WorkflowStatus.ATTENTION_REQUIRED:
            attention_event = MonitoringService(clock=self.clock).record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="red_team_suite",
                    workflow_run_id=run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.ATTENTION_REQUIRED,
                    status=WorkflowStatus.ATTENTION_REQUIRED,
                    message=self._summary_message(violations=violations),
                    related_artifact_ids=[violation.guardrail_violation_id for violation in violations],
                    notes=[f"requested_by={request.requested_by}"],
                ),
                output_root=monitoring_root,
            )
            storage_locations.append(attention_event.storage_location)
            pipeline_event_ids.append(attention_event.pipeline_event.pipeline_event_id)

        audit_log = AuditLoggingService(clock=self.clock).record_event(
            AuditEventRequest(
                event_type="red_team_suite_completed",
                actor_type="service",
                actor_id=self.capability_name,
                target_type="red_team_suite",
                target_id=run_id,
                action="execute",
                outcome=self._audit_outcome(workflow_status),
                reason=self._summary_message(violations=violations),
                request_id=run_id,
                status_before=WorkflowStatus.RUNNING.value,
                status_after=workflow_status.value,
                related_artifact_ids=[
                    *[case.red_team_case_id for case in cases],
                    *[violation.guardrail_violation_id for violation in violations],
                    *[finding.safety_finding_id for finding in findings],
                ],
                notes=[f"requested_by={request.requested_by}"],
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_log.storage_location)

        monitoring_response = MonitoringService(clock=self.clock).record_run_summary(
            RecordRunSummaryRequest(
                workflow_name="red_team_suite",
                workflow_run_id=run_id,
                service_name=self.capability_name,
                requested_by=request.requested_by,
                status=workflow_status,
                started_at=started_at,
                completed_at=self.clock.now(),
                storage_locations=storage_locations,
                produced_artifact_ids=[
                    *[case.red_team_case_id for case in cases],
                    *[violation.guardrail_violation_id for violation in violations],
                    *[finding.safety_finding_id for finding in findings],
                    audit_log.audit_log.audit_log_id,
                ],
                pipeline_event_ids=pipeline_event_ids,
                failure_messages=(
                    [violation.message for violation in violations if violation.blocking]
                    if workflow_status is WorkflowStatus.FAILED
                    else []
                ),
                attention_reasons=(
                    [self._summary_message(violations=violations)]
                    if workflow_status is WorkflowStatus.ATTENTION_REQUIRED
                    else []
                ),
                notes=notes,
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        storage_locations.extend(monitoring_response.storage_locations)
        return RunRedTeamSuiteResponse(
            red_team_cases=cases,
            guardrail_violations=violations,
            safety_findings=findings,
            run_summary=monitoring_response.run_summary,
            alert_records=monitoring_response.alert_records,
            audit_log=audit_log.audit_log,
            storage_locations=storage_locations,
            notes=notes,
        )

    def _load_workspace(self, request: RunRedTeamSuiteRequest) -> LoadedRedTeamWorkspace:
        """Load persisted artifacts needed by the deterministic red-team scenarios."""

        settings = get_settings()
        parsing_root = request.parsing_root or (settings.resolved_artifact_root / "parsing")
        research_root = request.research_root or (settings.resolved_artifact_root / "research")
        signal_root = request.signal_root or (settings.resolved_artifact_root / "signal_generation")
        portfolio_root = request.portfolio_root or (settings.resolved_artifact_root / "portfolio")
        review_root = request.review_root or (settings.resolved_artifact_root / "review")
        experiment_root = request.experiment_root or (settings.resolved_artifact_root / "experiments")
        return LoadedRedTeamWorkspace(
            research_briefs=load_models(
                root=research_root, category="research_briefs", model_cls=ResearchBrief
            ),
            evidence_assessments=load_models(
                root=research_root,
                category="evidence_assessments",
                model_cls=EvidenceAssessment,
            ),
            signals=load_models(root=signal_root, category="signals", model_cls=Signal),
            parsed_texts=load_models(root=parsing_root, category="parsed_text", model_cls=ParsedDocumentText),
            claims=load_models(root=parsing_root, category="claims", model_cls=ExtractedClaim),
            portfolio_proposals=load_models(
                root=portfolio_root,
                category="portfolio_proposals",
                model_cls=PortfolioProposal,
            ),
            paper_trades=load_models(root=portfolio_root, category="paper_trades", model_cls=PaperTrade),
            review_decisions=load_models(
                root=review_root,
                category="review_decisions",
                model_cls=ReviewDecision,
            ),
            experiments=load_models(root=experiment_root, category="experiments", model_cls=Experiment),
        )

    def _resolve_roots(self, request: RunRedTeamSuiteRequest) -> tuple[Path, Path, Path]:
        """Resolve red-team, monitoring, and audit roots for the suite run."""

        settings = get_settings()
        red_team_root = request.output_root or (settings.resolved_artifact_root / "red_team")
        monitoring_root = request.monitoring_root or (settings.resolved_artifact_root / "monitoring")
        audit_root = request.audit_root or (settings.resolved_artifact_root / "audit")
        return red_team_root, monitoring_root, audit_root

    def _workflow_status(self, *, violations: list[GuardrailViolation]) -> WorkflowStatus:
        """Derive the monitoring status from guardrail violations."""

        if any(
            violation.blocking or violation.severity is Severity.CRITICAL
            for violation in violations
        ):
            return WorkflowStatus.FAILED
        if violations:
            return WorkflowStatus.ATTENTION_REQUIRED
        return WorkflowStatus.SUCCEEDED

    def _summary_message(self, *, violations: list[GuardrailViolation]) -> str:
        """Build a short monitoring and audit summary message."""

        if not violations:
            return "No guardrail violations were detected."
        blocking_count = sum(1 for violation in violations if violation.blocking)
        return (
            f"{len(violations)} guardrail violations detected, including "
            f"{blocking_count} blocking violations."
        )

    def _audit_outcome(self, status: WorkflowStatus) -> AuditOutcome:
        """Map monitoring status to a simple audit outcome."""

        if status is WorkflowStatus.SUCCEEDED:
            return AuditOutcome.SUCCESS
        if status is WorkflowStatus.ATTENTION_REQUIRED:
            return AuditOutcome.WARNING
        return AuditOutcome.FAILURE
