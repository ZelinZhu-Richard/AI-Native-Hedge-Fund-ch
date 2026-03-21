"""Document ingestion service."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.ingestion.service import (
        DocumentIngestionRequest,
        DocumentIngestionResponse,
        FixtureIngestionRequest,
        FixtureIngestionResponse,
        IngestionService,
    )

__all__ = [
    "DocumentIngestionRequest",
    "DocumentIngestionResponse",
    "FixtureIngestionRequest",
    "FixtureIngestionResponse",
    "IngestionService",
]


def __getattr__(name: str) -> object:
    """Lazily expose ingestion service types without import-time cycles."""

    if name in __all__:
        from services.ingestion.service import (
            DocumentIngestionRequest,
            DocumentIngestionResponse,
            FixtureIngestionRequest,
            FixtureIngestionResponse,
            IngestionService,
        )

        exports = {
            "DocumentIngestionRequest": DocumentIngestionRequest,
            "DocumentIngestionResponse": DocumentIngestionResponse,
            "FixtureIngestionRequest": FixtureIngestionRequest,
            "FixtureIngestionResponse": FixtureIngestionResponse,
            "IngestionService": IngestionService,
        }
        return exports[name]
    raise AttributeError(name)
