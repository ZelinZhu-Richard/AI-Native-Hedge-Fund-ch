from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.schemas import AblationView, StrictModel
from libraries.time import Clock, SystemClock
from services.feature_store import (
    FeatureStoreService,
    RunFeatureMappingRequest,
    RunFeatureMappingResponse,
)
from services.signal_arbitration import (
    RunSignalArbitrationRequest,
    RunSignalArbitrationResponse,
    SignalArbitrationService,
)
from services.signal_generation import (
    RunSignalGenerationWorkflowRequest,
    RunSignalGenerationWorkflowResponse,
    SignalGenerationService,
)


class FeatureSignalPipelineResponse(StrictModel):
    """Typed response for the end-to-end Day 5 feature and signal pipeline."""

    feature_mapping: RunFeatureMappingResponse = Field(
        description="Feature-mapping workflow result."
    )
    signal_generation: RunSignalGenerationWorkflowResponse = Field(
        description="Signal-generation workflow result."
    )
    signal_arbitration: RunSignalArbitrationResponse = Field(
        description="Deterministic signal calibration and arbitration output."
    )


def run_feature_signal_pipeline(
    *,
    research_root: Path | None = None,
    parsing_root: Path | None = None,
    output_root: Path | None = None,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
    ablation_view: AblationView = AblationView.TEXT_ONLY,
    requested_by: str = "pipeline_feature_signal_generation",
    clock: Clock | None = None,
) -> FeatureSignalPipelineResponse:
    """Run the Day 5 deterministic feature and signal workflow."""

    settings = get_settings()
    resolved_artifact_root = settings.resolved_artifact_root
    resolved_research_root = research_root or (resolved_artifact_root / "research")
    resolved_parsing_root = parsing_root or (resolved_artifact_root / "parsing")
    resolved_output_root = output_root or (resolved_artifact_root / "signal_generation")
    resolved_clock = clock or SystemClock()

    feature_service = FeatureStoreService(clock=resolved_clock)
    signal_service = SignalGenerationService(clock=resolved_clock)
    arbitration_service = SignalArbitrationService(clock=resolved_clock)
    feature_mapping = feature_service.run_feature_mapping_workflow(
        RunFeatureMappingRequest(
            research_root=resolved_research_root,
            parsing_root=resolved_parsing_root,
            output_root=resolved_output_root,
            company_id=company_id,
            as_of_time=as_of_time,
            ablation_view=ablation_view,
            requested_by=requested_by,
        )
    )
    signal_generation = signal_service.run_signal_generation_workflow(
        RunSignalGenerationWorkflowRequest(
            feature_root=resolved_output_root,
            research_root=resolved_research_root,
            output_root=resolved_output_root,
            company_id=feature_mapping.company_id,
            as_of_time=as_of_time,
            ablation_view=ablation_view,
            requested_by=requested_by,
        )
    )
    signal_arbitration = arbitration_service.run_signal_arbitration(
        RunSignalArbitrationRequest(
            signal_root=resolved_output_root,
            research_root=resolved_research_root,
            output_root=resolved_output_root.parent / "signal_arbitration",
            company_id=feature_mapping.company_id,
            as_of_time=as_of_time,
            requested_by=requested_by,
        )
    )
    return FeatureSignalPipelineResponse(
        feature_mapping=feature_mapping,
        signal_generation=signal_generation,
        signal_arbitration=signal_arbitration,
    )
