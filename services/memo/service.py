from __future__ import annotations

from pydantic import Field

from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import Memo, MemoStatus, StrictModel
from libraries.utils import make_prefixed_id


class MemoGenerationRequest(StrictModel):
    """Request to generate a research memo from reviewed artifacts."""

    title: str = Field(description="Memo title.")
    audience: str = Field(description="Primary audience.")
    executive_summary: str = Field(description="Executive summary content.")
    related_hypothesis_ids: list[str] = Field(
        default_factory=list, description="Related hypotheses."
    )
    related_portfolio_proposal_id: str | None = Field(
        default=None,
        description="Related portfolio proposal identifier if applicable.",
    )
    requested_by: str = Field(description="Requester identifier.")


class MemoGenerationResponse(StrictModel):
    """Response containing the generated memo artifact."""

    memo: Memo = Field(description="Generated memo.")


class MemoGenerationService(BaseService):
    """Generate explainable, reviewable research memos."""

    capability_name = "memo"
    capability_description = (
        "Generates research memos from reviewed research and portfolio artifacts."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Hypothesis", "PortfolioProposal", "RiskCheck"],
            produces=["Memo"],
            api_routes=[],
        )

    def generate(self, request: MemoGenerationRequest) -> MemoGenerationResponse:
        """Generate a placeholder memo artifact."""

        now = self.clock.now()
        memo = Memo(
            memo_id=make_prefixed_id("memo"),
            title=request.title,
            status=MemoStatus.DRAFT,
            audience=request.audience,
            generated_at=now,
            author_agent_run_id=None,
            related_hypothesis_ids=request.related_hypothesis_ids,
            related_portfolio_proposal_id=request.related_portfolio_proposal_id,
            executive_summary=request.executive_summary,
            key_points=["Day 1 memo generation is a controlled placeholder."],
            key_risks=["All outputs require human review."],
            open_questions=["Source-linked evidence flow is still being built in Day 2."],
            content_uri=None,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="memo_generation_stub",
                upstream_artifact_ids=request.related_hypothesis_ids,
            ),
            created_at=now,
            updated_at=now,
        )
        return MemoGenerationResponse(memo=memo)
