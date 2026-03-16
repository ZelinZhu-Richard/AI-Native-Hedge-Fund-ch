"""Shared abstractions for services and agents."""

from libraries.core.agent_framework import AgentDescriptor
from libraries.core.provenance import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability

__all__ = ["AgentDescriptor", "BaseService", "ServiceCapability", "build_provenance"]
