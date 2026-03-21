"""Deterministic company entity-resolution and cross-source linking service."""

from services.entity_resolution.service import (
    EntityResolutionService,
    ResolveEntityWorkspaceRequest,
    ResolveEntityWorkspaceResponse,
)

__all__ = [
    "EntityResolutionService",
    "ResolveEntityWorkspaceRequest",
    "ResolveEntityWorkspaceResponse",
]
