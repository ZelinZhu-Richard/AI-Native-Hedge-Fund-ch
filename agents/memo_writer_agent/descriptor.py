from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="memo_writer_agent",
    role="assembles memo-ready research briefs and draft memo skeletons",
    objective="Turn structured research artifacts into concise review-ready briefs and draft memos without adding new claims, while preserving review and validation state.",
    inputs=["ResearchBrief"],
    outputs=["ResearchBrief", "Memo"],
    allowed_tools=["memo_service", "audit_service"],
    forbidden_actions=[
        "claim certainty without basis",
        "hide risk objections",
        "invent performance",
        "introduce unsupported prose",
    ],
    escalation_conditions=[
        "conflicting source evidence",
        "missing provenance",
        "material critique disagreement",
    ],
    failure_modes=["overselling", "loss of nuance", "missing evidence traceability", "review and validation state omitted"],
    evaluation_criteria=["explainability", "evidence coverage", "review usefulness"],
)
