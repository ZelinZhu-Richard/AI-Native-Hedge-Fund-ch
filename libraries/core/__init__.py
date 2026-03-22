"""Shared abstractions for services and agents."""

from libraries.core.agent_framework import AgentDescriptor
from libraries.core.local_artifacts import (
    ArtifactWorkspace,
    StoredLocalModel,
    ensure_directory_exists,
    ensure_file_exists,
    load_local_models,
    load_stored_local_models,
    persist_local_model,
    persist_local_text,
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.core.provenance import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability

__all__ = [
    "AgentDescriptor",
    "ArtifactWorkspace",
    "BaseService",
    "ServiceCapability",
    "StoredLocalModel",
    "build_provenance",
    "ensure_directory_exists",
    "ensure_file_exists",
    "load_local_models",
    "load_stored_local_models",
    "persist_local_model",
    "persist_local_text",
    "resolve_artifact_workspace",
    "resolve_artifact_workspace_from_stage_root",
]
