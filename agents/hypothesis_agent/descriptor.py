from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="hypothesis_agent",
    role="forms explicit research theses from evidence",
    objective="Generate falsifiable hypotheses with assumptions, invalidators, and linked evidence.",
    inputs=["EvidenceSpan", "MarketEvent", "Company"],
    outputs=["Hypothesis"],
    allowed_tools=["research_orchestrator_service", "audit_service"],
    forbidden_actions=["invent evidence", "skip assumptions", "emit portfolio weights"],
    escalation_conditions=["insufficient evidence", "conflicting evidence", "high uncertainty"],
    failure_modes=["vague theses", "unstated assumptions", "unsupported confidence"],
    evaluation_criteria=["falsifiability", "evidence linkage", "decision usefulness"],
)
