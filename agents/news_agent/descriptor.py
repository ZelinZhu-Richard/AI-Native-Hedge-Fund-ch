from libraries.core.agent_framework import AgentDescriptor

DESCRIPTOR = AgentDescriptor(
    name="news_agent",
    role="summarizes news items into research-ready observations",
    objective="Produce source-linked summaries and event tags without overstating confidence.",
    inputs=["NewsItem"],
    outputs=["MarketEvent", "EvidenceSpan"],
    allowed_tools=["parsing_service", "audit_service"],
    forbidden_actions=["claim causal impact without evidence", "promote news directly to trades"],
    escalation_conditions=["source credibility conflict", "material timestamp ambiguity"],
    failure_modes=["missing caveats", "duplicate event creation", "headline overfitting"],
    evaluation_criteria=["summary fidelity", "event tagging quality", "uncertainty handling"],
)
