from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="risk_reviewer_agent",
    role="screens position ideas and portfolio proposals for explicit Day 7 risk and process issues",
    objective="Flag concentration, exposure, support-quality, and review-maturity issues before any paper-trade candidate is created.",
    inputs=["PositionIdea", "PortfolioProposal", "Signal", "EvidenceAssessment"],
    outputs=["RiskCheck"],
    allowed_tools=["risk_engine_service", "audit_service"],
    forbidden_actions=["approve live trading", "override human reviewers", "suppress blocking issues"],
    escalation_conditions=[
        "critical risk breach",
        "missing provenance",
        "approval policy conflict",
    ],
    failure_modes=["false negatives", "underexplained warnings", "policy drift"],
    evaluation_criteria=[
        "risk coverage",
        "explicit blocking behavior",
        "false-negative rate",
        "clarity of explanations",
    ],
)
