from __future__ import annotations

from pydantic import Field

from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import Memo, MemoStatus, ResearchBrief, StrictModel
from libraries.utils import make_prefixed_id


class MemoGenerationRequest(StrictModel):
    """Request to generate a draft memo skeleton from a structured research brief."""

    research_brief: ResearchBrief = Field(description="Memo-ready research brief to render.")
    audience: str = Field(default="research_review", description="Primary audience.")
    requested_by: str = Field(description="Requester identifier.")
    author_agent_run_id: str | None = Field(
        default=None,
        description="Agent run that assembled the memo-ready brief when available.",
    )


class MemoGenerationResponse(StrictModel):
    """Response containing the generated memo artifact."""

    memo: Memo = Field(description="Generated memo.")


class MemoGenerationService(BaseService):
    """Generate explainable, reviewable research memos."""

    capability_name = "memo"
    capability_description = "Generates draft research memos from memo-ready research briefs."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["ResearchBrief"],
            produces=["Memo"],
            api_routes=[],
        )

    def generate(self, request: MemoGenerationRequest) -> MemoGenerationResponse:
        """Generate a structured memo skeleton from a research brief."""

        now = self.clock.now()
        brief = request.research_brief
        memo = Memo(
            memo_id=make_prefixed_id("memo"),
            title=brief.title,
            status=MemoStatus.DRAFT,
            audience=request.audience,
            generated_at=now,
            author_agent_run_id=request.author_agent_run_id,
            related_hypothesis_ids=[brief.hypothesis_id],
            related_portfolio_proposal_id=None,
            executive_summary=f"{brief.core_hypothesis} Counter-case: {brief.counter_hypothesis_summary}",
            key_points=[
                brief.context_summary,
                brief.core_hypothesis,
                *[
                    link.note or link.quote
                    for link in brief.supporting_evidence_links[:2]
                ],
            ],
            key_risks=brief.key_counterarguments,
            open_questions=brief.next_validation_steps,
            content_uri=None,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="memo_generation_from_research_brief",
                source_reference_ids=brief.provenance.source_reference_ids,
                upstream_artifact_ids=[
                    brief.research_brief_id,
                    brief.hypothesis_id,
                    brief.counter_hypothesis_id,
                ],
                agent_run_id=request.author_agent_run_id,
            ),
            created_at=now,
            updated_at=now,
        )
        return MemoGenerationResponse(memo=memo)
