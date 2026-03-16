from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="risk_reviewer_agent",
    role="screens proposals for policy and portfolio risk issues",
    objective="Flag concentration, liquidity, exposure, and process-risk issues for human review.",
    inputs=["PositionIdea", "PortfolioProposal", "Signal"],
    outputs=["RiskCheck"],
    allowed_tools=["risk_engine_service", "audit_service"],
    forbidden_actions=["approve live trading", "override human reviewers"],
    escalation_conditions=[
        "critical risk breach",
        "missing provenance",
        "approval policy conflict",
    ],
    failure_modes=["false negatives", "underexplained warnings", "policy drift"],
    evaluation_criteria=["risk coverage", "false-negative rate", "clarity of explanations"],
)
