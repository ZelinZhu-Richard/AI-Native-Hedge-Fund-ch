"""FastAPI route groups for the local inspection and coordination surface."""

from apps.api.routes.documents import router as documents_router
from apps.api.routes.monitoring import router as monitoring_router
from apps.api.routes.portfolio import router as portfolio_router
from apps.api.routes.reports import router as reports_router
from apps.api.routes.research import router as research_router
from apps.api.routes.review import router as review_router
from apps.api.routes.system import router as system_router
from apps.api.routes.workflows import router as workflows_router

__all__ = [
    "documents_router",
    "monitoring_router",
    "portfolio_router",
    "reports_router",
    "research_router",
    "review_router",
    "system_router",
    "workflows_router",
]
