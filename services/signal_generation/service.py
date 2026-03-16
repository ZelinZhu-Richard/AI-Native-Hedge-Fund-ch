from __future__ import annotations

from datetime import datetime

from pydantic import Field

from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import StrictModel
from libraries.utils import make_prefixed_id


class SignalGenerationRequest(StrictModel):
    """Request to build signals from reviewed hypotheses and point-in-time features."""

    company_id: str = Field(description="Covered company identifier.")
    hypothesis_ids: list[str] = Field(
        default_factory=list, description="Input hypothesis identifiers."
    )
    feature_ids: list[str] = Field(default_factory=list, description="Input feature identifiers.")
    as_of_time: datetime = Field(
        description="Maximum information time allowed for signal generation."
    )
    requested_by: str = Field(description="Requester identifier.")


class SignalGenerationResponse(StrictModel):
    """Response returned after accepting a signal generation request."""

    signal_batch_id: str = Field(description="Identifier for the signal generation batch.")
    signal_ids: list[str] = Field(default_factory=list, description="Reserved signal identifiers.")
    status: str = Field(description="Operational status.")
    review_required: bool = Field(description="Whether resulting signals require human review.")
    accepted_at: datetime = Field(description="UTC timestamp when the batch was accepted.")


class SignalGenerationService(BaseService):
    """Generate candidate signals from reviewed research artifacts."""

    capability_name = "signal_generation"
    capability_description = "Builds candidate signals from hypotheses and features."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Hypothesis", "Feature"],
            produces=["Signal", "SignalScore"],
            api_routes=[],
        )

    def generate_signals(self, request: SignalGenerationRequest) -> SignalGenerationResponse:
        """Reserve identifiers for a future signal generation batch."""

        return SignalGenerationResponse(
            signal_batch_id=make_prefixed_id("signalbatch"),
            signal_ids=[make_prefixed_id("sig")],
            status="queued",
            review_required=True,
            accepted_at=self.clock.now(),
        )
