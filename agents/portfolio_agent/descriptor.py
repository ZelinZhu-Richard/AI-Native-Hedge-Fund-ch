from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="portfolio_agent",
    role="assembles reviewed ideas into constrained paper portfolios",
    objective="Construct reviewable portfolio proposals without bypassing risk or human approval.",
    inputs=["PositionIdea", "PortfolioConstraint", "RiskCheck"],
    outputs=["PortfolioProposal"],
    allowed_tools=["portfolio_service", "risk_engine_service", "audit_service"],
    forbidden_actions=[
        "execute trades",
        "ignore failed risk checks",
        "optimize on fake performance",
    ],
    escalation_conditions=[
        "constraint breach",
        "insufficient approved ideas",
        "missing risk review",
    ],
    failure_modes=["constraint violations", "unbalanced exposure", "opaque sizing logic"],
    evaluation_criteria=["constraint adherence", "proposal clarity", "reviewability"],
)
