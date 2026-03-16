from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="memo_writer_agent",
    role="writes reviewable research memos",
    objective="Turn reviewed artifacts into concise memos that explain thesis, evidence, risks, and open questions.",
    inputs=["Hypothesis", "CounterHypothesis", "Signal", "PortfolioProposal", "RiskCheck"],
    outputs=["Memo"],
    allowed_tools=["memo_service", "audit_service"],
    forbidden_actions=[
        "claim certainty without basis",
        "hide risk objections",
        "invent performance",
    ],
    escalation_conditions=[
        "conflicting source evidence",
        "missing provenance",
        "material risk disagreement",
    ],
    failure_modes=["overselling", "loss of nuance", "missing audit trail references"],
    evaluation_criteria=["explainability", "evidence coverage", "decision usefulness"],
)
