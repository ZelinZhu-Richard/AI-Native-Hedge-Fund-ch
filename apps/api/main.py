from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI
from pydantic import Field

from agents.registry import list_agent_descriptors
from libraries.config import get_settings
from libraries.core.service_registry import build_service_registry
from libraries.logging import configure_logging
from libraries.schemas import Hypothesis, PaperTrade, PortfolioProposal, StrictModel
from libraries.time import isoformat_z, utc_now
from services.ingestion import DocumentIngestionRequest, DocumentIngestionResponse, IngestionService


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

    services: list[dict[str, object]] = Field(description="Registered service capabilities.")
    agents: list[dict[str, object]] = Field(description="Registered agent descriptors.")


class HypothesisListResponse(StrictModel):
    """Placeholder hypothesis listing response."""

    items: list[Hypothesis] = Field(
        default_factory=list, description="Hypotheses visible to the caller."
    )
    total: int = Field(description="Count of hypotheses returned.")


class PortfolioProposalListResponse(StrictModel):
    """Placeholder portfolio proposal listing response."""

    items: list[PortfolioProposal] = Field(
        default_factory=list,
        description="Portfolio proposals visible to the caller.",
    )
    total: int = Field(description="Count of portfolio proposals returned.")


class PaperTradeProposalListResponse(StrictModel):
    """Placeholder paper trade proposal listing response."""

    items: list[PaperTrade] = Field(
        default_factory=list,
        description="Paper trade proposals visible to the caller.",
    )
    total: int = Field(description="Count of paper trade proposals returned.")


settings = get_settings()
configure_logging(settings.log_level)
service_registry = build_service_registry()
app = FastAPI(
    title=settings.project_name,
    version=settings.app_version,
    description="Control-plane API for the ANHF Day 1 research platform.",
)


def _models_to_dicts(items: Sequence[StrictModel]) -> list[dict[str, object]]:
    """Convert Pydantic models into JSON-serializable dictionaries."""

    return [item.model_dump(mode="json") for item in items]


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return a simple health response."""

    return HealthResponse(status="ok", timestamp=isoformat_z(utc_now()))


@app.get("/version", response_model=VersionResponse, tags=["system"])
def version() -> VersionResponse:
    """Return project version metadata."""

    return VersionResponse(
        project_name=settings.project_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@app.get("/capabilities", response_model=CapabilityResponse, tags=["system"])
def capabilities() -> CapabilityResponse:
    """Return registered services and agent descriptors."""

    service_capabilities = [service.capability() for service in service_registry.values()]
    return CapabilityResponse(
        services=_models_to_dicts(service_capabilities),
        agents=_models_to_dicts(list_agent_descriptors()),
    )


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
    """Return placeholder hypothesis results."""

    return HypothesisListResponse(items=[], total=0)


@app.get(
    "/portfolio-proposals",
    response_model=PortfolioProposalListResponse,
    tags=["portfolio"],
)
def list_portfolio_proposals() -> PortfolioProposalListResponse:
    """Return placeholder portfolio proposal results."""

    return PortfolioProposalListResponse(items=[], total=0)


@app.get(
    "/paper-trades/proposals",
    response_model=PaperTradeProposalListResponse,
    tags=["paper-trading"],
)
def list_paper_trade_proposals() -> PaperTradeProposalListResponse:
    """Return placeholder paper trade proposal results."""

    return PaperTradeProposalListResponse(items=[], total=0)
