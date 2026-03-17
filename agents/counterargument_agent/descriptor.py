from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="counterargument_agent",
    role="stress-tests primary hypotheses as the thesis critic",
    objective="Produce a disciplined counter-hypothesis that challenges assumptions, missing evidence, and causal claims.",
    inputs=["Hypothesis", "EvidenceAssessment", "ExtractedRiskFactor", "ToneMarker"],
    outputs=["CounterHypothesis"],
    allowed_tools=["research_orchestrator_service", "audit_service"],
    forbidden_actions=["agree by default", "discard contradictory evidence", "invent a bearish narrative without support"],
    escalation_conditions=["no meaningful counter-case found", "evidence coverage too thin"],
    failure_modes=["weak critique", "straw-man counterarguments", "missing causal gaps"],
    evaluation_criteria=["adversarial strength", "evidence use", "gap surfacing quality"],
)
