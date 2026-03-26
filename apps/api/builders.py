from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeVar

from agents.registry import list_agent_descriptors
from libraries.config.settings import Settings, get_settings
from libraries.core import AgentDescriptor, ServiceCapability
from libraries.schemas import (
    APIResponseEnvelope,
    CapabilityDescriptor,
    DemoRunResult,
    HealthCheckStatus,
    InterfaceWarning,
    ServiceManifest,
    WorkflowInvocationResult,
    WorkflowStatus,
)
from pipelines.demo.end_to_end_demo import EndToEndDemoResponse
from services.daily_orchestration import RunDailyWorkflowResponse

TData = TypeVar("TData")


def build_response_envelope(
    *,
    data: TData,
    generated_at: datetime,
    notes: list[str] | None = None,
    warnings: list[InterfaceWarning] | None = None,
) -> APIResponseEnvelope[TData]:
    """Wrap one typed payload in the standard success envelope."""

    return APIResponseEnvelope[TData](
        data=data,
        notes=notes or [],
        warnings=warnings or [],
        generated_at=generated_at,
    )


def build_capability_descriptors(
    *,
    service_capabilities: list[ServiceCapability],
    agent_descriptors: list[AgentDescriptor] | None = None,
) -> list[CapabilityDescriptor]:
    """Build normalized capability descriptors for the current interface surface."""

    agents = agent_descriptors or list_agent_descriptors()
    descriptors = [
        *[_build_service_descriptor(capability) for capability in service_capabilities],
        *[_build_agent_descriptor(descriptor) for descriptor in agents],
        *_workflow_descriptors(),
    ]
    descriptors.sort(key=lambda descriptor: (descriptor.kind, descriptor.name))
    return descriptors


def build_service_manifest(
    *,
    generated_at: datetime,
    service_capabilities: list[ServiceCapability],
    settings: Settings | None = None,
) -> ServiceManifest:
    """Build the grounded interface manifest for the current local repo surface."""

    runtime_settings = settings or get_settings()
    return ServiceManifest(
        project_name=runtime_settings.project_name,
        environment=runtime_settings.environment,
        artifact_root=runtime_settings.resolved_artifact_root,
        generated_at=generated_at,
        capabilities=build_capability_descriptors(service_capabilities=service_capabilities),
        config_surface=_config_surface(runtime_settings),
        warnings=default_interface_warnings(),
    )


def build_demo_run_result(
    *,
    response: EndToEndDemoResponse,
    invocation_kind: Literal["api", "cli"],
) -> DemoRunResult:
    """Build a compact, interface-facing summary from the full demo response."""

    health_status = _derive_health_status(
        [check.status for check in response.health_checks.health_checks]
    )
    produced_artifact_ids = _dedupe(
        [
            response.portfolio_review.final_portfolio_proposal.portfolio_proposal_id,
            *(
                [response.portfolio_review.risk_summary.risk_summary_id]
                if response.portfolio_review.risk_summary is not None
                else []
            ),
            *(
                [response.portfolio_review.proposal_scorecard.proposal_scorecard_id]
                if response.portfolio_review.proposal_scorecard is not None
                else []
            ),
            *[idea.position_idea_id for idea in response.portfolio_review.final_position_ideas],
            *[trade.paper_trade_id for trade in response.portfolio_review.paper_trades],
            *[check.risk_check_id for check in response.portfolio_review.risk_checks],
            *[
                summary.run_summary_id
                for summary in response.recent_run_summaries.items
                if summary.workflow_name in {"fixture_ingestion", "evidence_extraction", "portfolio_review"}
            ],
            response.review_note.review_note.review_note_id,
            response.review_action.review_decision.review_decision_id,
            response.review_note.audit_log.audit_log_id,
            response.review_action.audit_log.audit_log_id,
        ]
    )
    warnings = [
        InterfaceWarning(
            warning_code="local_only",
            message="The demo interface is local only and does not expose live trading behavior.",
            scope="demo",
        ),
        InterfaceWarning(
            warning_code="synthetic_price_fixture",
            message="The default demo uses synthetic daily price fixtures for backtesting.",
            scope="demo",
        ),
        InterfaceWarning(
            warning_code="review_bound",
            message="The default demo remains review-bound and does not auto-promote paper trades.",
            scope="demo",
        ),
    ]
    return DemoRunResult(
        workflow_name="demo_end_to_end",
        invocation_kind=invocation_kind,
        workflow_run_id=response.demo_run_id,
        status=WorkflowStatus.ATTENTION_REQUIRED,
        artifact_root=response.base_root,
        storage_locations=response.portfolio_review.storage_locations,
        produced_artifact_ids=produced_artifact_ids,
        run_summary_ids=[summary.run_summary_id for summary in response.recent_run_summaries.items],
        notes=response.notes,
        warnings=warnings,
        demo_run_id=response.demo_run_id,
        manifest_path=response.manifest_path,
        company_id=response.company_id,
        portfolio_proposal_id=response.portfolio_review.final_portfolio_proposal.portfolio_proposal_id,
        review_queue_total=len(response.review_queue.queue_items),
        paper_trade_candidate_count=len(response.portfolio_review.paper_trades),
        health_status=health_status,
    )


def build_daily_workflow_result(
    *,
    response: RunDailyWorkflowResponse,
    invocation_kind: Literal["api", "cli"],
) -> WorkflowInvocationResult:
    """Build a compact, interface-facing summary from the daily workflow response."""

    warnings = [InterfaceWarning(
        warning_code="local_only",
        message="The daily workflow interface is a local coordination surface, not a scheduler or production control plane.",
        scope="daily_workflow",
    )]
    if response.workflow_execution.status is WorkflowStatus.ATTENTION_REQUIRED:
        warnings.append(
            InterfaceWarning(
                warning_code="review_required",
                message="The daily workflow completed in an attention_required stop state. Inspect run notes and manual-intervention requirements to distinguish a healthy review gate from a harder blocked stop.",
                scope="daily_workflow",
                related_ids=response.workflow_execution.produced_artifact_ids,
            )
        )
    return WorkflowInvocationResult(
        workflow_name="daily_workflow",
        invocation_kind=invocation_kind,
        workflow_run_id=response.workflow_execution.workflow_execution_id,
        status=response.workflow_execution.status,
        artifact_root=response.scheduled_run_config.artifact_roots["artifact_root"],
        storage_locations=response.storage_locations,
        produced_artifact_ids=response.workflow_execution.produced_artifact_ids,
        run_summary_ids=response.workflow_execution.linked_child_run_summary_ids,
        notes=response.notes,
        warnings=warnings,
    )


def default_interface_warnings() -> list[InterfaceWarning]:
    """Return the default interface-surface caveats."""

    return [
        InterfaceWarning(
            warning_code="local_only",
            message="This interface surface is local, filesystem-backed, and intended for inspection and demonstration.",
            scope="system",
        ),
        InterfaceWarning(
            warning_code="no_live_trading",
            message="Live trading and brokerage execution are intentionally not exposed.",
            scope="system",
        ),
        InterfaceWarning(
            warning_code="review_bound_downstream",
            message="Downstream portfolio and paper-trade flows remain explicitly review-bound.",
            scope="system",
        ),
    ]


def _build_service_descriptor(capability: ServiceCapability) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name=capability.name,
        kind="service",
        description=capability.description,
        inputs=capability.consumes,
        outputs=capability.produces,
        api_routes=capability.api_routes,
        cli_commands=[],
        config_keys=[],
        notes=[],
    )


def _build_agent_descriptor(descriptor: AgentDescriptor) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name=descriptor.name,
        kind="agent",
        description=descriptor.objective,
        inputs=descriptor.inputs,
        outputs=descriptor.outputs,
        api_routes=[],
        cli_commands=[],
        config_keys=[],
        notes=[descriptor.role],
    )


def _workflow_descriptors() -> list[CapabilityDescriptor]:
    return [
        CapabilityDescriptor(
            name="daily_workflow",
            kind="workflow",
            description="Run the local deterministic daily research-to-review operating workflow.",
            inputs=["artifact root", "fixtures root", "as_of_time", "ablation view"],
            outputs=["WorkflowExecution", "RunStep", "DailySystemReport"],
            api_routes=["POST /workflows/daily/run"],
            cli_commands=["nta daily run", "make daily-run"],
            config_keys=["ARTIFACT_ROOT", "DEFAULT_TIMEZONE"],
            notes=[
                "The default healthy local outcome is often attention_required, which indicates a visible review-bound stop rather than a workflow failure, because paper-trade candidates remain review-gated.",
                "Legacy compatibility alias: `anhf daily run` remains available during the CLI migration."
            ],
        ),
        CapabilityDescriptor(
            name="demo_end_to_end",
            kind="workflow",
            description="Run the deterministic local end-to-end demo over fixtures and synthetic prices.",
            inputs=["fixtures root", "price fixture path", "base root", "frozen time"],
            outputs=["demo manifest", "portfolio proposal", "monitoring run summaries"],
            api_routes=["POST /workflows/demo/run"],
            cli_commands=["nta demo run", "make demo"],
            config_keys=["ARTIFACT_ROOT", "DEFAULT_TIMEZONE"],
            notes=[
                "The default demo remains review-bound and does not imply autonomous paper-trade generation.",
                "Legacy compatibility alias: `anhf demo run` remains available during the CLI migration."
            ],
        ),
    ]


def _config_surface(settings: Settings) -> dict[str, str]:
    surface: dict[str, str] = {}
    for name, field in Settings.model_fields.items():
        alias = str(field.validation_alias or name).upper()
        value = getattr(settings, name)
        surface[alias] = str(value)
    surface["APP_VERSION"] = settings.app_version
    surface["RESOLVED_ARTIFACT_ROOT"] = str(settings.resolved_artifact_root)
    return surface


def _derive_health_status(statuses: list[HealthCheckStatus]) -> HealthCheckStatus:
    if any(status is HealthCheckStatus.FAIL for status in statuses):
        return HealthCheckStatus.FAIL
    if any(status is HealthCheckStatus.WARN for status in statuses):
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
