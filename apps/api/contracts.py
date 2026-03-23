from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.schemas import (
    AlertRecord,
    CapabilityDescriptor,
    DataRefreshMode,
    HealthCheck,
    Hypothesis,
    PaperTrade,
    PortfolioProposal,
    ResearchBrief,
    ReviewQueueItem,
    RunSummary,
    ServiceStatus,
    StrictModel,
)
from libraries.schemas.research import AblationView


class HealthPayload(StrictModel):
    """Liveness payload for the API."""

    status: str = Field(description="Overall API health status.")
    timestamp: str = Field(description="UTC timestamp in ISO-8601 format.")


class VersionPayload(StrictModel):
    """Version and environment metadata."""

    project_name: str = Field(description="Configured project name.")
    version: str = Field(description="Application version.")
    environment: str = Field(description="Runtime environment.")


class HealthDetailsPayload(StrictModel):
    """Structured local health and readiness payload."""

    status: str = Field(description="Overall health status.")
    timestamp: str = Field(description="UTC timestamp in ISO-8601 format.")
    health_checks: list[HealthCheck] = Field(default_factory=list)
    service_statuses: list[ServiceStatus] = Field(default_factory=list)
    open_alert_count: int = Field(description="Count of currently open alerts.")


class CapabilityListPayload(StrictModel):
    """Normalized capability listing payload."""

    items: list[CapabilityDescriptor] = Field(default_factory=list)
    total: int = Field(description="Count of descriptors returned.")


class HypothesisListPayload(StrictModel):
    """Artifact-backed hypothesis listing payload."""

    items: list[Hypothesis] = Field(default_factory=list)
    total: int = Field(description="Count of hypotheses returned.")


class ResearchBriefListPayload(StrictModel):
    """Artifact-backed research-brief listing payload."""

    items: list[ResearchBrief] = Field(default_factory=list)
    total: int = Field(description="Count of research briefs returned.")


class PortfolioProposalListPayload(StrictModel):
    """Artifact-backed portfolio proposal listing payload."""

    items: list[PortfolioProposal] = Field(default_factory=list)
    total: int = Field(description="Count of portfolio proposals returned.")


class PaperTradeListPayload(StrictModel):
    """Artifact-backed paper-trade listing payload."""

    items: list[PaperTrade] = Field(default_factory=list)
    total: int = Field(description="Count of paper trades returned.")


class ReviewQueuePayload(StrictModel):
    """Operator review queue payload."""

    items: list[ReviewQueueItem] = Field(default_factory=list)
    total: int = Field(description="Count of review queue items returned.")


class RunSummaryListPayload(StrictModel):
    """Recent monitoring run-summary payload."""

    items: list[RunSummary] = Field(default_factory=list)
    total: int = Field(description="Count of run summaries returned.")


class FailureSummaryPayload(StrictModel):
    """Recent failure and alert payload."""

    run_summaries: list[RunSummary] = Field(default_factory=list)
    alert_records: list[AlertRecord] = Field(default_factory=list)
    total_runs: int = Field(description="Count of returned run summaries.")
    total_alerts: int = Field(description="Count of returned alert records.")


class ServiceStatusListPayload(StrictModel):
    """Current service-status payload."""

    items: list[ServiceStatus] = Field(default_factory=list)
    total: int = Field(description="Count of returned service statuses.")


class RunDemoRequest(StrictModel):
    """Explicit request to run the end-to-end local demo through the API."""

    fixtures_root: Path | None = Field(default=None)
    price_fixture_path: Path | None = Field(default=None)
    base_root: Path | None = Field(default=None)
    requested_by: str = Field(default="api_demo_run")
    frozen_time: datetime | None = Field(default=None)


class RunDailyWorkflowApiRequest(StrictModel):
    """Explicit request to run the local daily workflow through the API."""

    artifact_root: Path | None = Field(default=None)
    fixtures_root: Path | None = Field(default=None)
    data_refresh_mode: DataRefreshMode = Field(default=DataRefreshMode.FIXTURE_REFRESH)
    company_id: str | None = Field(default=None)
    as_of_time: datetime | None = Field(default=None)
    generate_memo_skeleton: bool = Field(default=True)
    include_retrieval_context: bool = Field(default=True)
    ablation_view: AblationView = Field(default=AblationView.TEXT_ONLY)
    assumed_reference_prices: dict[str, float] = Field(default_factory=dict)
    requested_by: str = Field(default="api_daily_workflow")
