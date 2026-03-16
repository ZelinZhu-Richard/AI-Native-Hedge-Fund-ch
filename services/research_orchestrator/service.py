from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import StrictModel
from libraries.time import utc_now
from libraries.utils import make_prefixed_id


class ResearchCycleRequest(StrictModel):
    """Request to launch a coordinated research cycle for a company or theme."""

    objective: str = Field(description="Research objective to pursue.")
    company_id: str | None = Field(
        default=None, description="Primary company under coverage when applicable."
    )
    trigger_type: str = Field(description="Trigger for the cycle, such as filing or news.")
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts that triggered the cycle.",
    )
    as_of_time: datetime = Field(description="UTC time defining the cycle information boundary.")
    requested_by: str = Field(description="Requester identifier.")


class ResearchCycleResponse(StrictModel):
    """Response returned after accepting a research cycle."""

    research_cycle_id: str = Field(description="Canonical research cycle identifier.")
    status: str = Field(description="Operational status.")
    started_at: datetime = Field(description="UTC timestamp when orchestration began.")
    planned_agents: list[str] = Field(
        default_factory=list,
        description="Agents planned for the cycle.",
    )


class ResearchOrchestrationService(BaseService):
    """Coordinate multi-step research workflows across services and agents."""

    capability_name = "research_orchestrator"
    capability_description = "Coordinates research cycles while preserving review boundaries."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Document", "MarketEvent", "ResearchCycleRequest"],
            produces=["AgentRun", "Hypothesis", "Memo"],
            api_routes=[],
        )

    def start_cycle(self, request: ResearchCycleRequest) -> ResearchCycleResponse:
        """Start a new research cycle."""

        return ResearchCycleResponse(
            research_cycle_id=make_prefixed_id("cycle"),
            status="started",
            started_at=utc_now(),
            planned_agents=[
                "filing_ingestion_agent",
                "transcript_agent",
                "news_agent",
                "hypothesis_agent",
                "counterargument_agent",
                "memo_writer_agent",
            ],
        )
