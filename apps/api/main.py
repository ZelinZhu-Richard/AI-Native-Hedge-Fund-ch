from __future__ import annotations

from fastapi import FastAPI

from apps.api.errors import register_exception_handlers
from apps.api.routes import (
    documents_router,
    monitoring_router,
    portfolio_router,
    reports_router,
    research_router,
    review_router,
    system_router,
    workflows_router,
)
from apps.api.state import api_clock
from libraries.config import get_settings
from libraries.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.project_name,
    version=settings.app_version,
    description=(
        "Inspection API for the local Nexus Tensor Alpha research operating system, including "
        "artifact-backed review, monitoring, reporting, and workflow coordination surfaces."
    ),
)

register_exception_handlers(app, now_provider=api_clock.now)
app.include_router(system_router)
app.include_router(monitoring_router)
app.include_router(documents_router)
app.include_router(research_router)
app.include_router(portfolio_router)
app.include_router(review_router)
app.include_router(reports_router)
app.include_router(workflows_router)
