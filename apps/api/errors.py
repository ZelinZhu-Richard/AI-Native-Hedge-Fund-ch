from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from libraries.schemas import ErrorResponse


def register_exception_handlers(app: object, *, now_provider: Callable[[], datetime]) -> None:
    """Register consistent exception handlers on the FastAPI application."""

    fastapi_app = app

    @fastapi_app.exception_handler(RequestValidationError)  # type: ignore[attr-defined]
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        error = ErrorResponse(
            error_code="validation_error",
            message="Request validation failed.",
            details=[
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            ],
            path=request.url.path,
            timestamp=now_provider(),
        )
        return JSONResponse(status_code=422, content=error.model_dump(mode="json"))

    @fastapi_app.exception_handler(HTTPException)  # type: ignore[attr-defined]
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        details = exc.detail if isinstance(exc.detail, list) else [str(exc.detail)]
        error = ErrorResponse(
            error_code=_http_error_code(exc.status_code),
            message=str(exc.detail),
            details=details,
            path=request.url.path,
            timestamp=now_provider(),
        )
        return JSONResponse(status_code=exc.status_code, content=error.model_dump(mode="json"))

    @fastapi_app.exception_handler(ValueError)  # type: ignore[attr-defined]
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        error = ErrorResponse(
            error_code="invalid_request",
            message=str(exc),
            details=[str(exc)],
            path=request.url.path,
            timestamp=now_provider(),
        )
        return JSONResponse(status_code=400, content=error.model_dump(mode="json"))


def _http_error_code(status_code: int) -> str:
    if status_code == 404:
        return "not_found"
    if status_code == 400:
        return "invalid_request"
    if status_code == 422:
        return "validation_error"
    return "http_error"
