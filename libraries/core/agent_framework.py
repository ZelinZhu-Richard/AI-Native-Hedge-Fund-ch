from __future__ import annotations

from pydantic import Field

from libraries.schemas.base import StrictModel


class AgentDescriptor(StrictModel):
    """Machine-readable description of an agent's scope and controls."""

    name: str = Field(description="Unique agent name.")
    role: str = Field(description="Short statement of agent role.")
    objective: str = Field(description="Primary objective for the agent.")
    inputs: list[str] = Field(default_factory=list, description="Primary input artifact types.")
    outputs: list[str] = Field(default_factory=list, description="Primary output artifact types.")
    allowed_tools: list[str] = Field(
        default_factory=list, description="Tools or services the agent may use."
    )
    forbidden_actions: list[str] = Field(
        default_factory=list,
        description="Actions the agent must never perform.",
    )
    escalation_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that require human escalation.",
    )
    failure_modes: list[str] = Field(
        default_factory=list,
        description="Known failure modes to monitor.",
    )
    evaluation_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria used to evaluate the agent.",
    )
