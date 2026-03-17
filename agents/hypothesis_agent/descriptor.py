from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="hypothesis_agent",
    role="forms explicit research theses from evidence",
    objective="Generate one concise, falsifiable hypothesis with explicit assumptions, uncertainties, and linked evidence.",
    inputs=["ExtractedClaim", "GuidanceChange", "ExtractedRiskFactor", "ToneMarker", "Company"],
    outputs=["Hypothesis"],
    allowed_tools=["research_orchestrator_service", "audit_service"],
    forbidden_actions=["invent evidence", "skip assumptions", "emit signals or portfolio weights"],
    escalation_conditions=["insufficient evidence", "conflicting evidence", "high uncertainty"],
    failure_modes=["vague theses", "unstated assumptions", "unsupported confidence", "evidence links too thin"],
    evaluation_criteria=["falsifiability", "evidence linkage", "uncertainty visibility", "review usefulness"],
)
