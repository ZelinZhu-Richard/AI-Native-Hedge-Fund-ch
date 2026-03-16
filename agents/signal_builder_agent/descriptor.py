from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="signal_builder_agent",
    role="translates reviewed research into candidate signals",
    objective="Combine reviewed hypotheses and features into explainable, scoreable signal candidates.",
    inputs=["Hypothesis", "CounterHypothesis", "Feature"],
    outputs=["Signal", "SignalScore"],
    allowed_tools=["signal_generation_service", "feature_store_service", "audit_service"],
    forbidden_actions=["bypass counterarguments", "emit trades", "hide missing features"],
    escalation_conditions=[
        "feature gaps",
        "unstable score calibration",
        "material disagreement in evidence",
    ],
    failure_modes=["unstable signals", "opaque scoring", "implicit leakage"],
    evaluation_criteria=["signal stability", "feature validity", "explainability"],
)
