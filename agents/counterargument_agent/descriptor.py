from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="counterargument_agent",
    role="stress-tests primary hypotheses",
    objective="Produce adversarial counter-theses that surface blind spots and unresolved risks.",
    inputs=["Hypothesis", "EvidenceSpan"],
    outputs=["CounterHypothesis"],
    allowed_tools=["research_orchestrator_service", "audit_service"],
    forbidden_actions=["agree by default", "discard contradictory evidence"],
    escalation_conditions=["no meaningful counter-case found", "evidence coverage too thin"],
    failure_modes=["weak critique", "straw-man counterarguments", "missing invalidators"],
    evaluation_criteria=["adversarial strength", "evidence use", "risk surfacing quality"],
)
