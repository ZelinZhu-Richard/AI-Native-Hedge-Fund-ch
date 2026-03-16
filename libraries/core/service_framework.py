from __future__ import annotations

from abc import ABC

from pydantic import Field

from libraries.schemas.base import StrictModel
from libraries.time import Clock, SystemClock


class ServiceCapability(StrictModel):
    """Describes what a service does and which artifacts it owns."""

    name: str = Field(description="Unique service name.")
    description: str = Field(description="Human-readable description of service responsibility.")
    consumes: list[str] = Field(
        default_factory=list,
        description="Artifact types or requests this service consumes.",
    )
    produces: list[str] = Field(
        default_factory=list,
        description="Artifact types or responses this service produces.",
    )
    api_routes: list[str] = Field(
        default_factory=list,
        description="API routes or capabilities exposed to operators.",
    )


class BaseService(ABC):
    """Base class for application services."""

    capability_name: str
    capability_description: str

    def __init__(self, clock: Clock | None = None) -> None:
        """Initialize a service with an explicit time source."""

        self.clock = clock or SystemClock()

    def capability(self) -> ServiceCapability:
        """Return service metadata for discovery and operational visibility."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
        )
