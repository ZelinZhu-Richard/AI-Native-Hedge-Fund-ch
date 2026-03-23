from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.builders import build_response_envelope
from apps.api.contracts import ReviewQueuePayload
from apps.api.state import api_clock, service_registry
from libraries.schemas import APIResponseEnvelope, ReviewContext, ReviewTargetType
from services.operator_review import (
    AddReviewNoteRequest,
    AddReviewNoteResponse,
    ApplyReviewActionRequest,
    ApplyReviewActionResponse,
    AssignReviewRequest,
    AssignReviewResponse,
    GetReviewContextRequest,
    ListReviewQueueRequest,
    OperatorReviewService,
)

router = APIRouter(prefix="/reviews", tags=["review"])


@router.get("/queue", response_model=APIResponseEnvelope[ReviewQueuePayload])
def list_review_queue() -> APIResponseEnvelope[ReviewQueuePayload]:
    """Return operator review queue items backed by persisted artifacts."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    response = service.list_review_queue(ListReviewQueueRequest())
    return build_response_envelope(
        data=ReviewQueuePayload(items=response.items, total=response.total),
        generated_at=api_clock.now(),
        notes=response.notes,
    )


@router.get("/context/{target_type}/{target_id}", response_model=APIResponseEnvelope[ReviewContext])
def get_review_context(
    target_type: ReviewTargetType,
    target_id: str,
) -> APIResponseEnvelope[ReviewContext]:
    """Return the derived operator-console review context for one target."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    try:
        context = service.get_review_context(
            GetReviewContextRequest(
                target_type=target_type,
                target_id=target_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_response_envelope(data=context, generated_at=api_clock.now())


@router.post("/notes", response_model=APIResponseEnvelope[AddReviewNoteResponse])
def add_review_note(
    request: AddReviewNoteRequest,
) -> APIResponseEnvelope[AddReviewNoteResponse]:
    """Persist one operator review note."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    response = service.add_review_note(request)
    return build_response_envelope(data=response, generated_at=api_clock.now())


@router.post("/assignments", response_model=APIResponseEnvelope[AssignReviewResponse])
def assign_review(
    request: AssignReviewRequest,
) -> APIResponseEnvelope[AssignReviewResponse]:
    """Assign one review queue item to one operator."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    response = service.assign_review(request)
    return build_response_envelope(data=response, generated_at=api_clock.now())


@router.post("/actions", response_model=APIResponseEnvelope[ApplyReviewActionResponse])
def apply_review_action(
    request: ApplyReviewActionRequest,
) -> APIResponseEnvelope[ApplyReviewActionResponse]:
    """Apply one explicit review action to a reviewable target."""

    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    response = service.apply_review_action(request)
    return build_response_envelope(data=response, generated_at=api_clock.now())
