from __future__ import annotations

from pathlib import Path

from libraries.config import get_settings
from libraries.time import Clock, SystemClock
from services.research_orchestrator import (
    ResearchOrchestrationService,
    RunResearchWorkflowRequest,
    RunResearchWorkflowResponse,
)


def run_hypothesis_workflow_pipeline(
    *,
    parsing_root: Path | None = None,
    ingestion_root: Path | None = None,
    output_root: Path | None = None,
    company_id: str | None = None,
    generate_memo_skeleton: bool = True,
    include_retrieval_context: bool = True,
    requested_by: str = "pipeline_daily_research",
    clock: Clock | None = None,
) -> RunResearchWorkflowResponse:
    """Run the Day 4 deterministic hypothesis and critique workflow."""

    settings = get_settings()
    resolved_artifact_root = settings.resolved_artifact_root
    service = ResearchOrchestrationService(clock=clock or SystemClock())
    return service.run_research_workflow(
        RunResearchWorkflowRequest(
            parsing_root=parsing_root or (resolved_artifact_root / "parsing"),
            ingestion_root=ingestion_root or (resolved_artifact_root / "ingestion"),
            output_root=output_root or (resolved_artifact_root / "research"),
            company_id=company_id,
            generate_memo_skeleton=generate_memo_skeleton,
            include_retrieval_context=include_retrieval_context,
            requested_by=requested_by,
        )
    )
