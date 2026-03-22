from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from fastapi import FastAPI, HTTPException
from pydantic import Field

from agents.registry import list_agent_descriptors
from libraries.config import get_settings
from libraries.core import AgentDescriptor, ServiceCapability
from libraries.core.service_registry import build_service_registry
from libraries.logging import configure_logging
from libraries.schemas import (
    AlertRecord,
    HealthCheck,
    Hypothesis,
    PaperTrade,
    PortfolioProposal,
    ReviewContext,
    ReviewQueueItem,
    ReviewTargetType,
    RunSummary,
    ServiceStatus,
    StrictModel,
)
from libraries.schemas.base import TimestampedModel
from libraries.time import SystemClock, isoformat_z
from services.ingestion import DocumentIngestionRequest, DocumentIngestionResponse, IngestionService
from services.monitoring import (
    GetServiceStatusesRequest,
    ListRecentFailureSummariesRequest,
    ListRecentRunSummariesRequest,
    MonitoringService,
    RunHealthChecksRequest,
)
from services.operator_review import (
    AddReviewNoteRequest,
    AddReviewNoteResponse,
    ApplyReviewActionRequest,
    ApplyReviewActionResponse,
    AssignReviewRequest,
    AssignReviewResponse,
    GetReviewContextRequest,
    ListReviewQueueRequest,
    OperatorReviewService,
)

T = TypeVar("T", bound=TimestampedModel)


class HealthResponse(StrictModel):
    """Liveness response for the API."""

    status: str = Field(description="Overall API health status.")
    timestamp: str = Field(description="UTC timestamp in ISO-8601 format.")


class VersionResponse(StrictModel):
    """Version and environment metadata."""

    project_name: str = Field(description="Configured project name.")
    version: str = Field(description="Application version.")
    environment: str = Field(description="Runtime environment.")


class CapabilityResponse(StrictModel):
    """Service and agent discovery response."""

    services: list[ServiceCapability] = Field(description="Registered service capabilities.")
    agents: list[AgentDescriptor] = Field(description="Registered agent descriptors.")


class HypothesisListResponse(StrictModel):
    """Artifact-backed hypothesis listing response."""

    items: list[Hypothesis] = Field(
        default_factory=list, description="Hypotheses visible to the caller."
    )
    total: int = Field(description="Count of hypotheses returned.")


class PortfolioProposalListResponse(StrictModel):
    """Artifact-backed portfolio proposal listing response."""

    items: list[PortfolioProposal] = Field(
        default_factory=list,
        description="Portfolio proposals visible to the caller.",
    )
    total: int = Field(description="Count of portfolio proposals returned.")


class PaperTradeProposalListResponse(StrictModel):
    """Artifact-backed paper-trade listing response."""

    items: list[PaperTrade] = Field(
        default_factory=list,
        description="Paper trade proposals visible to the caller.",
    )
    total: int = Field(description="Count of paper trade proposals returned.")


class ReviewQueueApiResponse(StrictModel):
    """Operator review queue response."""

    items: list[ReviewQueueItem] = Field(default_factory=list)
    total: int = Field(description="Count of review queue items returned.")
    notes: list[str] = Field(default_factory=list)


class HealthDetailsResponse(StrictModel):
    """Structured health and readiness response."""

    status: str = Field(description="Overall health status.")
    timestamp: str = Field(description="UTC timestamp in ISO-8601 format.")
    health_checks: list[HealthCheck] = Field(default_factory=list)
    service_statuses: list[ServiceStatus] = Field(default_factory=list)
    open_alert_count: int = Field(description="Count of currently open alerts.")
    notes: list[str] = Field(default_factory=list)


class RunSummaryListResponse(StrictModel):
    """Recent monitoring run summaries."""

    items: list[RunSummary] = Field(default_factory=list)
    total: int = Field(description="Count of run summaries returned.")
    notes: list[str] = Field(default_factory=list)


class FailureSummaryApiResponse(StrictModel):
    """Recent failed or attention-required run summaries."""

    run_summaries: list[RunSummary] = Field(default_factory=list)
    alert_records: list[AlertRecord] = Field(default_factory=list)
    total_runs: int = Field(description="Count of returned run summaries.")
    total_alerts: int = Field(description="Count of returned alert records.")
    notes: list[str] = Field(default_factory=list)


class ServiceStatusApiResponse(StrictModel):
    """Derived current service statuses."""

    items: list[ServiceStatus] = Field(default_factory=list)
    total: int = Field(description="Count of returned service statuses.")
    notes: list[str] = Field(default_factory=list)


settings = get_settings()
api_clock = SystemClock()
configure_logging(settings.log_level)
service_registry = build_service_registry(clock=api_clock)
app = FastAPI(
    title=settings.project_name,
    version=settings.app_version,
    description=(
        "Inspection API for the local ANHF research operating system, including "
        "artifact-backed review, monitoring, and paper-trading coordination surfaces."
    ),
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return a simple health response."""

    return HealthResponse(status="ok", timestamp=isoformat_z(api_clock.now()))


@app.get("/health/details", response_model=HealthDetailsResponse, tags=["system"])
def health_details() -> HealthDetailsResponse:
    """Return structured local health and readiness information."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.run_health_checks(RunHealthChecksRequest())
    status = (
        "fail"
        if any(check.status.value == "fail" for check in response.health_checks)
        else ("warn" if any(check.status.value == "warn" for check in response.health_checks) else "ok")
    )
    return HealthDetailsResponse(
        status=status,
        timestamp=isoformat_z(api_clock.now()),
        health_checks=response.health_checks,
        service_statuses=response.service_statuses,
        open_alert_count=sum(item.open_alert_count for item in response.service_statuses),
        notes=response.notes,
    )


@app.get("/version", response_model=VersionResponse, tags=["system"])
def version() -> VersionResponse:
    """Return project version metadata."""

    runtime_settings = get_settings()
    return VersionResponse(
        project_name=runtime_settings.project_name,
        version=runtime_settings.app_version,
        environment=runtime_settings.environment,
    )


@app.get("/capabilities", response_model=CapabilityResponse, tags=["system"])
def capabilities() -> CapabilityResponse:
    """Return registered services and agent descriptors."""

    service_capabilities = [service.capability() for service in service_registry.values()]
    return CapabilityResponse(
        services=service_capabilities,
        agents=list_agent_descriptors(),
    )


@app.get(
    "/monitoring/run-summaries/recent",
    response_model=RunSummaryListResponse,
    tags=["monitoring"],
)
def list_recent_run_summaries(
    service_name: str | None = None,
    workflow_name: str | None = None,
    limit: int = 20,
) -> RunSummaryListResponse:
    """Return recent persisted monitoring run summaries."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.list_recent_run_summaries(
        ListRecentRunSummariesRequest(
            service_name=service_name,
            workflow_name=workflow_name,
            limit=limit,
        )
    )
    return RunSummaryListResponse(items=response.items, total=response.total, notes=response.notes)


@app.get(
    "/monitoring/failures/recent",
    response_model=FailureSummaryApiResponse,
    tags=["monitoring"],
)
def list_recent_failure_summaries(
    service_name: str | None = None,
    limit: int = 20,
) -> FailureSummaryApiResponse:
    """Return recent failed or attention-required runs and open alerts."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.list_recent_failure_summaries(
        ListRecentFailureSummariesRequest(
            service_name=service_name,
            limit=limit,
        )
    )
    return FailureSummaryApiResponse(
        run_summaries=response.run_summaries,
        alert_records=response.alert_records,
        total_runs=response.total_runs,
        total_alerts=response.total_alerts,
        notes=response.notes,
    )


@app.get("/monitoring/services", response_model=ServiceStatusApiResponse, tags=["monitoring"])
def list_service_statuses() -> ServiceStatusApiResponse:
    """Return derived current statuses for registered services."""

    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.get_service_statuses(GetServiceStatusesRequest())
    return ServiceStatusApiResponse(items=response.items, total=response.total, notes=response.notes)


@app.post(
    "/documents/ingest",
    response_model=DocumentIngestionResponse,
    tags=["documents"],
)
def ingest_document(request: DocumentIngestionRequest) -> DocumentIngestionResponse:
    """Queue a document for future ingestion and normalization."""

    service = service_registry["ingestion"]
    assert isinstance(service, IngestionService)
    return service.ingest_document(request)


@app.get("/hypotheses", response_model=HypothesisListResponse, tags=["research"])
def list_hypotheses() -> HypothesisListResponse:
    """Return persisted research hypotheses when they exist."""

    items = _load_persisted_models(
        _artifact_root() / "research" / "hypotheses",
        Hypothesis,
    )
    return HypothesisListResponse(items=items, total=len(items))


@app.get(
    "/portfolio-proposals",
    response_model=PortfolioProposalListResponse,
    tags=["portfolio"],
)
def list_portfolio_proposals() -> PortfolioProposalListResponse:
    """Return persisted portfolio proposals when they exist."""

    items = _load_persisted_models(
        _artifact_root() / "portfolio" / "portfolio_proposals",
        PortfolioProposal,
    )
    return PortfolioProposalListResponse(items=items, total=len(items))


@app.get(
    "/paper-trades/proposals",
    response_model=PaperTradeProposalListResponse,
    tags=["paper-trading"],
)
def list_paper_trade_proposals() -> PaperTradeProposalListResponse:
    """Return persisted paper-trade proposals when they exist."""

    items = _load_persisted_models(
        _artifact_root() / "portfolio" / "paper_trades",
        PaperTrade,
    )
    return PaperTradeProposalListResponse(items=items, total=len(items))


@app.get("/reviews/queue", response_model=ReviewQueueApiResponse, tags=["review"])
def list_review_queue() -> ReviewQueueApiResponse:
    """Return operator review queue items backed by persisted artifacts."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    response = service.list_review_queue(ListReviewQueueRequest())
    return ReviewQueueApiResponse(items=response.items, total=response.total, notes=response.notes)


@app.get(
    "/reviews/context/{target_type}/{target_id}",
    response_model=ReviewContext,
    tags=["review"],
)
def get_review_context(target_type: ReviewTargetType, target_id: str) -> ReviewContext:
    """Return the derived operator-console review context for one target."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    try:
        return service.get_review_context(
            GetReviewContextRequest(
                target_type=target_type,
                target_id=target_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/reviews/notes", response_model=AddReviewNoteResponse, tags=["review"])
def add_review_note(request: AddReviewNoteRequest) -> AddReviewNoteResponse:
    """Persist one operator review note."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    try:
        return service.add_review_note(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/reviews/assignments", response_model=AssignReviewResponse, tags=["review"])
def assign_review(request: AssignReviewRequest) -> AssignReviewResponse:
    """Assign one review queue item to one operator."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    try:
        return service.assign_review(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/reviews/actions", response_model=ApplyReviewActionResponse, tags=["review"])
def apply_review_action(request: ApplyReviewActionRequest) -> ApplyReviewActionResponse:
    """Apply one explicit review action to a reviewable target."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    try:
        return service.apply_review_action(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _artifact_root() -> Path:
    """Resolve the current artifact root from runtime settings."""

    return get_settings().resolved_artifact_root


def _load_persisted_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load persisted artifacts for API inspection surfaces."""

    if not directory.exists():
        return []
    models = [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
    return sorted(models, key=lambda model: model.created_at, reverse=True)
