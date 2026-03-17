from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="portfolio_agent",
    role="maps eligible signals into reviewable position ideas and constrained portfolio proposals",
    objective="Construct inspectable portfolio proposals with explicit sizing rules, evidence linkage, and review gates.",
    inputs=["Signal", "ResearchBrief", "EvidenceAssessment", "PortfolioConstraint"],
    outputs=["PositionIdea", "PortfolioProposal"],
    allowed_tools=["portfolio_service", "risk_engine_service", "audit_service"],
    forbidden_actions=[
        "execute trades",
        "ignore failed risk checks",
        "optimize on fake performance",
        "hide candidate signal status",
    ],
    escalation_conditions=[
        "constraint breach",
        "missing company symbol",
        "insufficient evidence linkage",
        "missing risk review",
    ],
    failure_modes=["constraint violations", "unbalanced exposure", "opaque sizing logic"],
    evaluation_criteria=[
        "constraint adherence",
        "evidence linkage completeness",
        "proposal clarity",
        "reviewability",
    ],
)
