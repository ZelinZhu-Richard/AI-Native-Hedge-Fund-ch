from __future__ import annotations

from fastapi import APIRouter

from apps.api.builders import (
    build_daily_workflow_result,
    build_demo_run_result,
    build_response_envelope,
)
from apps.api.contracts import RunDailyWorkflowApiRequest, RunDemoRequest
from apps.api.state import api_clock
from libraries.schemas import APIResponseEnvelope, DemoRunResult, WorkflowInvocationResult
from pipelines.daily_operations import run_daily_workflow
from pipelines.demo import run_end_to_end_demo

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/demo/run", response_model=APIResponseEnvelope[DemoRunResult])
def run_demo(request: RunDemoRequest) -> APIResponseEnvelope[DemoRunResult]:
    """Run the deterministic local end-to-end demo through the API."""

    response = run_end_to_end_demo(
        fixtures_root=request.fixtures_root,
        price_fixture_path=request.price_fixture_path,
        base_root=request.base_root,
        requested_by=request.requested_by,
        frozen_time=request.frozen_time,
    )
    result = build_demo_run_result(response=response, invocation_kind="api")
    return build_response_envelope(
        data=result,
        generated_at=api_clock.now(),
        notes=result.notes,
    )


@router.post("/daily/run", response_model=APIResponseEnvelope[WorkflowInvocationResult])
def run_daily(request: RunDailyWorkflowApiRequest) -> APIResponseEnvelope[WorkflowInvocationResult]:
    """Run the deterministic local daily workflow through the API."""

    response = run_daily_workflow(
        artifact_root=request.artifact_root,
        fixtures_root=request.fixtures_root,
        data_refresh_mode=request.data_refresh_mode,
        company_id=request.company_id,
        as_of_time=request.as_of_time,
        generate_memo_skeleton=request.generate_memo_skeleton,
        include_retrieval_context=request.include_retrieval_context,
        ablation_view=request.ablation_view,
        assumed_reference_prices=request.assumed_reference_prices,
        requested_by=request.requested_by,
    )
    result = build_daily_workflow_result(response=response, invocation_kind="api")
    return build_response_envelope(
        data=result,
        generated_at=api_clock.now(),
        notes=result.notes,
    )
