from __future__ import annotations

from pathlib import Path

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import RetrievalContext, RetrievalQuery, StrictModel
from services.research_memory.indexing import build_catalog, search_catalog
from services.research_memory.loaders import load_research_memory_workspace


class SearchResearchMemoryRequest(StrictModel):
    """Read-only request to search persisted research artifacts."""

    workspace_root: Path = Field(description="Base workspace root containing artifact subdirectories.")
    research_root: Path | None = Field(
        default=None,
        description="Optional override for the persisted research artifact root.",
    )
    parsing_root: Path | None = Field(
        default=None,
        description="Optional override for the persisted parsing artifact root.",
    )
    ingestion_root: Path | None = Field(
        default=None,
        description="Optional override for the normalized ingestion artifact root.",
    )
    review_root: Path | None = Field(
        default=None,
        description="Optional override for the review artifact root.",
    )
    experiments_root: Path | None = Field(
        default=None,
        description="Optional override for the experiment-registry root.",
    )
    backtesting_root: Path | None = Field(
        default=None,
        description="Optional override for the backtesting artifact root.",
    )
    query: RetrievalQuery = Field(description="Structured retrieval query.")


class SearchResearchMemoryResponse(StrictModel):
    """Structured read-only response from the retrieval layer."""

    retrieval_context: RetrievalContext = Field(
        description="Advisory retrieval context for the query."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes surfaced by the retrieval layer.",
    )


class ResearchMemoryService(BaseService):
    """Search real persisted research artifacts with metadata-first deterministic retrieval."""

    capability_name = "research_memory"
    capability_description = (
        "Searches persisted evidence, research artifacts, experiments, and review notes."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=[
                "EvidenceSpan",
                "Hypothesis",
                "CounterHypothesis",
                "ResearchBrief",
                "Memo",
                "Experiment",
                "ReviewNote",
            ],
            produces=["RetrievalContext"],
            api_routes=[],
        )

    def search_research_memory(
        self,
        request: SearchResearchMemoryRequest,
    ) -> SearchResearchMemoryResponse:
        """Search persisted artifacts without mutating or generating new artifacts."""

        workspace = load_research_memory_workspace(
            workspace_root=request.workspace_root,
            research_root=request.research_root,
            parsing_root=request.parsing_root,
            ingestion_root=request.ingestion_root,
            review_root=request.review_root,
            experiments_root=request.experiments_root,
            backtesting_root=request.backtesting_root,
        )
        catalog = build_catalog(workspace=workspace, clock=self.clock)
        retrieval_context = search_catalog(
            catalog=catalog,
            query=request.query,
            clock=self.clock,
        )
        return SearchResearchMemoryResponse(
            retrieval_context=retrieval_context,
            notes=list(retrieval_context.notes),
        )
